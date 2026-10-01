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
                        timing_trusted: params.timing_trusted,
                    ] + spec
                    [ meta, file(ds.fasta, checkIfExists: true), file(ds.tax, checkIfExists: true) ]
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
}
