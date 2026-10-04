// One run.json per (dataset, condition, replicate), in the shape scripts/05_concordance.py,
// 06_cutoff_sensitivity.py and 03_plot.py already read.
process COLLECTRUN {
    tag "${meta.dataset}/${meta.condition}/rep${meta.rep}"
    label 'process_single'

    // Pinned to a patch version, not the 3.12 tag. This module writes every run.json, so a floating
    // tag would mean the parser that produced a result is not recoverable from the repo. 3.12.12
    // exists on conda-forge, quay.io/biocontainers and depot.galaxyproject.org, so all three paths
    // pin to the same thing; a digest would have pinned only the docker one.
    conda "conda-forge::python=3.12.12"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/python:3.12.12' :
        'quay.io/biocontainers/python:3.12.12' }"

    input:
    tuple val(meta), path(mis), path(timing), path(runlog), path(stdoutlog), path(inputs)

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
        --inputs ${inputs} \\
        --out ${meta.run_name}/run.json

    cp ${mis} ${runlog} ${stdoutlog} ${meta.run_name}/
    """

    stub:
    """
    mkdir -p ${meta.run_name}
    echo '{}' > ${meta.run_name}/run.json
    """
}
