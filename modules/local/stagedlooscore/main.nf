// Stage 4 of 4: score every placed fold into the .mis the analysis scripts read.
//
// Serial, like the first two, and reported separately for the same reason. It needs the whole task
// directory back, so the placement shards' outputs are collected here.
process STAGEDLOOSCORE {
    tag "${meta.dataset}/${meta.condition}/rep${meta.rep}"
    label 'process_timed'

    conda "bioconda::sativa-epang=0.10.2"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/sativa-epang:0.10.2--py314hab16a5f_0' :
        'quay.io/biocontainers/sativa-epang:0.10.2--py314hab16a5f_0' }"

    input:
    tuple val(meta), path(refjson), path(manifest), path(model), path(folds, stageAs: 'placed/*')

    output:
    tuple val(meta), path("run.mis")     , emit: mis
    tuple val(meta), path("timing.json") , emit: timing
    tuple val(meta), path("stage.log")   , emit: log

    when:
    task.ext.when == null || task.ext.when

    script:
    // Empty args is a bug, not a default. Without -x the tool prints its usage message and exits 0,
    // so the stage reports success and produces nothing; a withName selector that failed to match
    // this process did exactly that.
    def args = task.ext.args ?: error("${task.process} has no ext.args; check conf/modules.config")
    """
    mkdir -p run.l1o_tasks
    cp ${manifest} run.l1o_tasks/manifest.json
    cp ${model} run.l1o_tasks/model
    for d in placed/fold_*; do
        mkdir -p run.l1o_tasks/\$(basename \$d)
        cp -L \$d/* run.l1o_tasks/\$(basename \$d)/
    done

    # Every fold the manifest declares has to be here, or the score is taken over part of the
    # database and nothing says so. The shards are collected by the workflow and a lost one would
    # otherwise be silent.
    want=\$(python3 -c "import json; print(json.load(open('run.l1o_tasks/manifest.json'))['n_folds'])")
    got=\$(ls -d run.l1o_tasks/fold_* | wc -l)
    # -eq, not =: `wc -l` pads its output on some platforms and "       3" = "3" is false.
    [ "\$got" -eq "\$want" ] || { echo "collected \$got of \$want folds" >&2; exit 1; }

    export SATIVA_L1O_ENGINE=${meta.engine}
    export OMP_NUM_THREADS=${meta.threads}

    _timeit.py --stdout stage.log -- \\
        sativa-epang -r ${refjson} -T ${meta.threads} -n run -o . ${args} \\
            -stage loo-score -taskdir \$PWD/run.l1o_tasks \\
        > timing.json
    """

    stub:
    """
    mkdir -p run.l1o_tasks
    cp ${manifest} run.l1o_tasks/manifest.json
    want=\$(python3 -c "import json; print(json.load(open('run.l1o_tasks/manifest.json'))['n_folds'])")
    got=\$(ls -d placed/fold_* | wc -l)
    # -eq, not =: `wc -l` pads its output on some platforms and "       3" = "3" is false.
    [ "\$got" -eq "\$want" ] || { echo "collected \$got of \$want folds" >&2; exit 1; }
    echo ';stub' > run.mis
    echo '{"wall_sec": 0.0, "returncode": 0, "timed_out": false, "max_rss_mb": 0.0}' > timing.json
    touch stage.log
    """
}
