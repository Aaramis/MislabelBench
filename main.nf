#!/usr/bin/env nextflow

/*
 * sativa-epang benchmark.
 *
 * The grid is (dataset x condition x replicate). Each cell runs one tool once and produces
 * one run.json, which is what the analysis scripts in bin/ already read.
 */

include { SATIVA      } from './modules/local/sativa/main'
include { SATIVAEPANG } from './modules/local/sativaepang/main'
include { COLLECTRUN  } from './modules/local/collectrun/main'

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

    ch_runs = SATIVA.out.mis.mix(SATIVAEPANG.out.mis)
        .join(SATIVA.out.timing.mix(SATIVAEPANG.out.timing))
        .join(SATIVA.out.log.mix(SATIVAEPANG.out.log))
        .join(SATIVA.out.stdout.mix(SATIVAEPANG.out.stdout))

    COLLECTRUN(ch_runs)

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
