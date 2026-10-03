// Stage 1 of 4 of the distributed leave-one-out: build the reference tree and model.
//
// The four stages exist because only the third distributes, and reporting them separately is what
// makes the speedup readable rather than flattered by the serial parts. See DISTRIBUTION.md.
process STAGEDREFERENCE {
    tag "${meta.dataset}/${meta.condition}/rep${meta.rep}"
    label 'process_timed'

    conda "bioconda::sativa-epang=0.10.2"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/sativa-epang:0.10.2--py314hab16a5f_0' :
        'quay.io/biocontainers/sativa-epang:0.10.2--py314hab16a5f_0' }"

    input:
    tuple val(meta), path(fasta), path(tax)

    output:
    tuple val(meta), path("run.refjson")   , emit: refjson
    tuple val(meta), path("run.model")     , emit: model
    tuple val(meta), path("timing.json")   , emit: timing
    tuple val(meta), path("stage.log")     , emit: log
    path "versions.yml"                    , emit: versions, topic: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    """
    mkdir -p tmp
    export SATIVA_L1O_ENGINE=${meta.engine}
    export OMP_NUM_THREADS=${meta.threads}

    _timeit.py --stdout stage.log -- \\
        sativa-epang \\
            -s ${fasta} -t ${tax} \\
            -T ${meta.threads} -n run -o . -tmpdir \$PWD/tmp \\
            ${args} -stage reference \\
        > timing.json

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        sativa-epang: \$(sativa-epang --version | cut -d' ' -f2)
    END_VERSIONS
    """

    stub:
    """
    echo '{}' > run.refjson
    echo 'model' > run.model
    echo '{"wall_sec": 0.0, "returncode": 0, "timed_out": false, "max_rss_mb": 0.0}' > timing.json
    touch stage.log
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        sativa-epang: stub
    END_VERSIONS
    """
}
