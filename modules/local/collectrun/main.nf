// One run.json per (dataset, condition, replicate), in the shape scripts/05_concordance.py,
// 06_cutoff_sensitivity.py and 03_plot.py already read.
process COLLECTRUN {
    tag "${meta.dataset}/${meta.condition}/rep${meta.rep}"
    label 'process_single'

    conda "conda-forge::python=3.12"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/python:3.12' :
        'quay.io/biocontainers/python:3.12' }"

    input:
    tuple val(meta), path(mis), path(timing), path(runlog), path(stdoutlog)

    output:
    tuple val(meta), path("${meta.run_name}/run.json"), emit: run
    path "${meta.run_name}"                           , emit: dir

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    mkdir -p ${meta.run_name}
    cat > meta.json <<'META_EOF'
    ${groovy.json.JsonOutput.toJson(meta)}
    META_EOF

    collect_run.py \\
        --meta meta.json \\
        --timing ${timing} \\
        --mis ${mis} \\
        --log ${runlog} \\
        --out ${meta.run_name}/run.json

    cp ${mis} ${runlog} ${stdoutlog} ${meta.run_name}/
    """

    stub:
    """
    mkdir -p ${meta.run_name}
    echo '{}' > ${meta.run_name}/run.json
    """
}
