// sativa-epang, the fork under test. Same CLI as upstream; the engine and the fold count are
// chosen through the environment, which is how the fork exposes them.
process SATIVAEPANG {
    tag "${meta.dataset}/${meta.condition}/rep${meta.rep}"
    label 'process_timed'

    conda "bioconda::sativa-epang=0.10.2"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/sativa-epang:0.10.2--py314hab16a5f_0' :
        'quay.io/biocontainers/sativa-epang:0.10.2--py314hab16a5f_0' }"

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
    // epang_l1o.py caps K at the leaf count, so a K above n means one sequence per fold,
    // which is the strict leave-one-out.
    def folds = meta.folds ? "export SATIVA_EPANG_FOLDS=${meta.folds}" : ''
    """
    mkdir -p run tmp
    cp ${fasta} ${tax} run/

    export SATIVA_L1O_ENGINE=${meta.engine}
    ${folds}
    export OMP_NUM_THREADS=${meta.threads}
    export OPENBLAS_NUM_THREADS=${meta.threads}
    export MKL_NUM_THREADS=${meta.threads}

    _timeit.py --cwd run --stdout run/stdout.log -- \\
        sativa-epang \\
            -s ${fasta.name} \\
            -t ${tax.name} \\
            -T ${meta.threads} \\
            -n ${meta.run_name} \\
            -tmpdir \$PWD/tmp \\
            ${args} \\
        > timing.json

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        sativa-epang: \$(sativa-epang --version | cut -d' ' -f2)
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
        sativa-epang: \$(sativa-epang --version | cut -d' ' -f2)
        python: \$(python3 --version | sed 's/Python //')
    END_VERSIONS
    """
}
