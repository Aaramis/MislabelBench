// The placement files a run would otherwise discard, kept as an output of their own.
//
// A process rather than a publishDir on the tool processes: three stub runs and one cluster run
// with a publishDir carrying `pattern: 'run/*.jplace'` on SATIVA came back without a file and
// without a word, whatever the entry's form, and a copy done by a process is a copy that fails
// loudly or not at all. One task per (cell, origin): upstream's two jplace files from the SATIVA
// run, or one placement shard's folds from the staged path, each with the tree its edge numbers
// refer to and the query it placed.
process KEEPPLACEMENTS {
    tag "${meta.run_name}/${origin}"
    label 'process_single'

    conda "conda-forge::python=3.12.12"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/python:3.12.12' :
        'quay.io/biocontainers/python:3.12.12' }"

    input:
    tuple val(meta), val(origin), path(files, stageAs: 'in/*')

    output:
    tuple val(meta), path("${meta.run_name}/${origin}"), emit: kept

    script:
    """
    mkdir -p ${meta.run_name}/${origin}
    # jplace, the tree the edge numbers refer to, and the query: per fold on the staged path, two
    # files at the top for upstream. Anything else a fold holds stays behind.
    find -L in -type f \\( -name '*.jplace' -o -name 'ref.nwk' -o -name 'query.fasta' \\) \\
        | while read -r f; do
            rel=\${f#in/}
            mkdir -p "${meta.run_name}/${origin}/\$(dirname "\$rel")"
            cp -L "\$f" "${meta.run_name}/${origin}/\$rel"
        done
    n=\$(find ${meta.run_name}/${origin} -name '*.jplace' | wc -l)
    [ "\$n" -gt 0 ] || { echo "no jplace among the files handed to KEEPPLACEMENTS" >&2; exit 1; }
    echo "kept \$n placement file(s) for ${meta.run_name}/${origin}"
    """

    stub:
    """
    mkdir -p ${meta.run_name}/${origin}
    touch ${meta.run_name}/${origin}/stub.jplace
    """
}
