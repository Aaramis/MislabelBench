// Unmodified SATIVA, the reference this benchmark compares against.
// Version and build are pinned here, not resolved at run time: the whole point is that a
// reader can install the same package.
process SATIVA {
    tag "${meta.dataset}/${meta.condition}/rep${meta.rep}"
    label 'process_timed'

    conda "bioconda::sativa=0.9.3"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/sativa:0.9.3--py312h031d066_0' :
        'quay.io/biocontainers/sativa:0.9.3--py312h031d066_0' }"

    input:
    tuple val(meta), path(fasta), path(tax)

    output:
    tuple val(meta), path("run/${meta.run_name}.mis"), emit: mis
    tuple val(meta), path("timing.json")             , emit: timing
    tuple val(meta), path("run/${meta.run_name}.log"), emit: log
    tuple val(meta), path("run/stdout.log")          , emit: stdout
    path "versions.yml"                              , emit: versions, topic: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    // Only the -T we ask for. Without this a BLAS picks its own thread count and the
    // timing stops meaning what it says.
    """
    mkdir -p run tmp
    cp ${fasta} ${tax} run/

    export OMP_NUM_THREADS=${meta.threads}
    export OPENBLAS_NUM_THREADS=${meta.threads}
    export MKL_NUM_THREADS=${meta.threads}

    _timeit.py --cwd run --stdout run/stdout.log -- \\
        sativa.py \\
            -s ${fasta.name} \\
            -t ${tax.name} \\
            -T ${meta.threads} \\
            -n ${meta.run_name} \\
            -tmpdir \$PWD/tmp \\
            ${args} \\
        > timing.json

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        sativa: 0.9.3
        python: \$(python3 --version | sed 's/Python //')
    END_VERSIONS
    """

    stub:
    """
    mkdir -p run
    touch run/${meta.run_name}.mis run/${meta.run_name}.log run/stdout.log
    echo '{"wall_sec": 0.0, "returncode": 0, "timed_out": false, "max_rss_mb": 0.0}' > timing.json
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        sativa: 0.9.3
        python: \$(python3 --version | sed 's/Python //')
    END_VERSIONS
    """
}
