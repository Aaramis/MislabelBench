#!/usr/bin/env nextflow

/*
 * sativa-epang benchmark.
 *
 * The grid is (dataset x condition x replicate). Each cell runs one tool once and produces
 * one run.json, which is what the analysis scripts in bin/ already read.
 */

include { SATIVA            } from './modules/local/sativa/main'
include { SATIVAEPANG       } from './modules/local/sativaepang/main'
include { COLLECTRUN        } from './modules/local/collectrun/main'
include { STAGEDREFERENCE   } from './modules/local/stagedreference/main'
include { STAGEDLOOTASKS    } from './modules/local/stagedlootasks/main'
include { STAGEDLOOPLACE    } from './modules/local/stagedlooplace/main'
include { STAGEDLOOSCORE    } from './modules/local/stagedlooscore/main'
include { KEEPPLACEMENTS    } from './modules/local/keepplacements/main'

// A manifest's relative paths are relative to the project, not to wherever the job was launched
// from. Each job now launches from its own directory so that several can run at once, and without
// this a manifest written with repo-relative paths would be looked for under .nf/<job>/ instead.
// checkIfExists turns that into a clear error rather than a silent one, but the right behaviour is
// to find the file.
def resolvePath(String p) {
    file(p.startsWith('/') ? p : "${projectDir}/${p}", checkIfExists: true)
}

workflow {

    def manifest = new groovy.json.JsonSlurper().parse(file(params.datasets_json))
    def wanted   = params.datasets == 'all' ? null : params.datasets.toString().tokenize(',')*.trim()
    def conds    = params.conditions == 'all'
        ? params.condition_specs.keySet() as List
        : params.conditions.toString().tokenize(',')*.trim()

    conds.each { c ->
        if (!params.condition_specs.containsKey(c)) {
            error "unknown condition '${c}'. Known: ${params.condition_specs.keySet().join(', ')}"
        }
    }

    def datasets = manifest.datasets.findAll { !wanted || it.name in wanted }
    if (!datasets) {
        error "no dataset matched '${params.datasets}' in ${params.datasets_json}"
    }

    // One channel element per cell of the grid.
    ch_cells = channel.fromList(
        datasets.collectMany { ds ->
            conds.collectMany { cond ->
                (1..(params.replicates as int)).collect { rep ->
                    def spec = params.condition_specs[cond]
                    def meta = [
                        dataset       : ds.name,
                        n_seqs        : ds.n_seqs,
                        aln_len       : ds.aln_len,
                        condition     : cond,
                        rep           : rep,
                        run_name      : "${ds.name}__${cond}__rep${rep}",
                        timing_trusted: params.timed,
                    ] + spec
                    [ meta, resolvePath(ds.fasta), resolvePath(ds.tax) ]
                }
            }
        }
    )

    ch_by_impl = ch_cells.branch { meta, _fasta, _tax ->
        upstream: meta.impl == 'sativa'
        fork    : meta.impl == 'sativaepang'
    }

    SATIVA(ch_by_impl.upstream)
    SATIVAEPANG(ch_by_impl.fork)

    // The same tool again, as four stages, which is the only way the distribution claim is
    // exercised by the harness rather than by a shell script. Off by default: it produces the same
    // .mis by a longer route, so it is a check and a measurement and not the way to run the grid.
    if (params.staged) {
        // A timed staged run needs each task in its own allocation, or the shards share a node and
        // the seconds mean nothing -- and the queueSize cap that normally prevents that is lifted
        // on this path precisely because serialising the shards would remove what is measured.
        if (params.timed && !workflow.profile.tokenize(',').contains('ifb')) {
            error "a timed staged run needs -profile ifb, so that each task is its own Slurm job"
        }

        // The stages wait for the monolithic run of the same cell. Both consume ch_by_impl.fork, so
        // without this they are submitted together -- 48 ms apart, measured in
        // trace-staged_timed_f25 -- and STAGEDREFERENCE and the control then build the same
        // reference tree at the same time, each taking 71 s where one alone takes 42.5.
        // The join is on meta, so a cell whose monolithic run failed never reaches the stages, which
        // is what the count guard below would report.
        STAGEDREFERENCE(
            ch_by_impl.fork
                .join(SATIVAEPANG.out.mis)
                .map { meta, fasta, tax, mis -> tuple(meta, fasta, tax) }
        )
        STAGEDLOOTASKS(
            STAGEDREFERENCE.out.refjson
                .join(STAGEDREFERENCE.out.model)
                .join(ch_by_impl.fork.map { meta, fasta, tax -> tuple(meta, fasta, tax) })
        )

        // Folds into shards, inside one flatMap over a cell's complete fold list. Grouping this way
        // rather than with a join means there is nothing to lose: every shard of a cell is built
        // from the one element that holds all of that cell's folds.
        //
        // The shards are strides -- shard i takes folds i, i+T, i+2T -- because that is the form
        // -folds takes and it lets one invocation cover a whole shard. T is derived from
        // folds_per_job rather than set directly, so that a cell with fewer folds than asked for
        // still gets one shard.
        ch_shards = STAGEDLOOTASKS.out.folds
            .join(STAGEDLOOTASKS.out.manifest)
            .join(STAGEDLOOTASKS.out.model)
            // man and mod, not manifest and model: `manifest` is already a name in the workflow
            // scope, taken by the config's manifest block, and the parser says so.
            .flatMap { meta, folds, man, mod ->
                // Numeric order, not name order. The tool names folds fold_000 ... with three
                // digits, so past a thousand folds fold_1000 sorts before fold_101 and a stride
                // over the sorted names is not the stride -folds i/N takes over fold numbers: the
                // shard stages one set and the tool asks for another, and the run dies on the first
                // fold it cannot find -- FileNotFoundError on fold_101, 29 folds into a 2 023-fold
                // Kexact cell. Twenty-five folds never showed it, since 000 to 024 sort both ways.
                def number = { f -> (f.name =~ /\d+/)[0] as int }
                def all = (folds instanceof List ? folds : [folds]).sort { number.call(it) }
                // Integer arithmetic, not a cast: the config parser rejects `(int) Math.ceil(...)`.
                def per = Math.max(params.folds_per_job as int, 1)
                def shards = Math.max((all.size() + per - 1).intdiv(per), 1)
                (0..<shards).collect { i ->
                    def mine = (i..<all.size()).step(shards).collect { all[it] }
                    // What the tool will look for is every fold whose number is i modulo the shard
                    // count; refuse here, with the fold named, rather than three minutes into it.
                    def off = mine.findAll { number.call(it) % shards != i }
                    if (off) {
                        error "shard ${i} of ${shards} for ${meta.run_name} holds ${off[0].name}, " +
                              "whose number is not ${i} modulo ${shards}: the fold order is not numeric"
                    }
                    tuple(meta + [shard: i, n_shards: shards], man, mod, mine)
                }
            }

        STAGEDLOOPLACE(ch_shards)

        // Back to one element per cell, with the shard keys dropped so the groups re-form on the
        // cell's own meta.
        //
        // groupKey and not a bare groupTuple. The comment here used to say that groupTuple needs the
        // size or it waits for the whole channel, and that n_shards was carried in the meta for
        // exactly that -- while passing n_shards as a tuple element, which groupTuple does not read.
        // So every cell's scoring waited for every other cell's shards: harmless on a one-cell timing
        // run, and on a grid it moves all the scoring to the end. groupKey(key, n) is the mechanism
        // for a size that differs per key, and .target unwraps it so the joins below still see a
        // plain meta map.
        ch_placed = STAGEDLOOPLACE.out.folds
            .map { meta, folds ->
                def key = meta.findAll { k, v -> !(k in ['shard', 'n_shards']) }
                tuple(groupKey(key, meta.n_shards as int), folds)
            }
            .groupTuple()
            .map { key, folds -> tuple(key.target, folds.flatten()) }

        STAGEDLOOSCORE(
            STAGEDREFERENCE.out.refjson
                .join(STAGEDLOOTASKS.out.manifest)
                .join(STAGEDLOOTASKS.out.model)
                .join(ch_placed)
        )

        // Same guarantee as the single-process path below: as many scored cells as were asked for.
        def expected_staged = datasets.size() * conds.count { params.condition_specs[it].impl == 'sativaepang' } * (params.replicates as int)
        STAGEDLOOSCORE.out.mis.count().subscribe { n ->
            if (n != expected_staged) {
                error "staged path scored ${n} cells for ${expected_staged} fork cells"
            }
        }
    }

    ch_runs = SATIVA.out.mis.mix(SATIVAEPANG.out.mis)
        .join(SATIVA.out.timing.mix(SATIVAEPANG.out.timing))
        .join(SATIVA.out.log.mix(SATIVAEPANG.out.log))
        .join(SATIVA.out.stdout.mix(SATIVAEPANG.out.stdout))
        .join(SATIVA.out.inputs.mix(SATIVAEPANG.out.inputs))

    COLLECTRUN(ch_runs)

    // The placement files, on request. Upstream's come from its own run; the fork's from the staged
    // path's shards, one task per shard, since its monolithic run removes them itself.
    if (params.keep) {
        ch_keep = SATIVA.out.placements.map { meta, files -> tuple(meta, 'upstream', files) }
        if (params.staged) {
            ch_keep = ch_keep.mix(STAGEDLOOPLACE.out.folds.map { meta, folds ->
                tuple(meta.findAll { k, v -> !(k in ['shard', 'n_shards']) },
                      "shard${meta.shard}of${meta.n_shards}", folds)
            })
        }
        KEEPPLACEMENTS(ch_keep)
    }

    // join() pairs on the meta map and silently drops whatever finds no partner, so a cell that
    // lost one of its four outputs would never reach COLLECTRUN and the grid would look complete
    // with one cell missing from it. Counting what arrived is the only place that shows.
    def expected = datasets.size() * conds.size() * (params.replicates as int)
    COLLECTRUN.out.run.count().subscribe { n ->
        if (n != expected) {
            error "collected ${n} run records for ${expected} cells: a cell lost an output before COLLECTRUN"
        }
    }
}
