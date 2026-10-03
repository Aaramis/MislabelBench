// Stage 2 of 4: write one task directory per fold.
//
// Each fold directory holds the alignment minus that fold's leaves, which is why the whole
// directory is 275 MB on 7051 sequences while the placements it leads to are 9 MB. The folds are
// emitted one channel element each so the next stage can take a group of them rather than all of
// them; manifest.json and model are emitted separately because every group needs both.
process STAGEDLOOTASKS {
    tag "${meta.dataset}/${meta.condition}/rep${meta.rep}"
    label 'process_timed'

    conda "bioconda::sativa-epang=0.10.2"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/sativa-epang:0.10.2--py314hab16a5f_0' :
        'quay.io/biocontainers/sativa-epang:0.10.2--py314hab16a5f_0' }"

    input:
    // run.model is not optional and not cosmetic. The tool looks for <name>.model beside the
    // refjson, and without it the log says "EPA-ng model: GTR+G" instead of naming the file: it
    // falls back to a default substitution model, writes no model into the task directory, and
    // exits 0. Every fold would then be placed under a model the reference stage did not fit, and
    // the .mis would differ from the single-process path for a reason that has nothing to do with
    // distributing anything. The declared output run.l1o_tasks/model is what caught it.
    tuple val(meta), path(refjson), path(model), path(fasta), path(tax)

    output:
    tuple val(meta), path("run.l1o_tasks/manifest.json"), emit: manifest
    tuple val(meta), path("run.l1o_tasks/model")        , emit: model
    tuple val(meta), path("run.l1o_tasks/fold_*")       , emit: folds
    tuple val(meta), path("timing.json")                , emit: timing
    tuple val(meta), path("stage.log")                  , emit: log

    when:
    task.ext.when == null || task.ext.when

    script:
    // The fold count is a property of the condition, as in the single-process path. The tool caps
    // it at the leaf count, so a value above n means one sequence per fold.
    def folds = meta.folds ? "export SATIVA_EPANG_FOLDS=${meta.folds}" : ''
    def foldOrder = meta.fold_order ? "export SATIVA_EPANG_FOLD_ORDER=${meta.fold_order}" : ''
    """
    export SATIVA_L1O_ENGINE=${meta.engine}
    ${folds}
    ${foldOrder}
    export OMP_NUM_THREADS=${meta.threads}

    _timeit.py --stdout stage.log -- \\
        sativa-epang -r ${refjson} -T ${meta.threads} -n run -o . -stage loo-tasks \\
        > timing.json

    # Said plainly here rather than left to Nextflow's missing-output message, because the cause
    # and the symptom are far apart: a fallback model produces no model file at all.
    grep -q 'EPA-ng model: .*run.model' stage.log || {
        echo 'loo-tasks did not use the fitted model; stage.log says:' >&2
        grep 'EPA-ng model' stage.log >&2
        exit 1
    }
    """

    stub:
    """
    mkdir -p run.l1o_tasks
    echo '[epang-l1o] EPA-ng model: run.model' > stage.log
    echo '{"n_folds": 3}' > run.l1o_tasks/manifest.json
    echo 'model' > run.l1o_tasks/model
    for i in 000 001 002; do
        mkdir -p run.l1o_tasks/fold_\$i
        echo 'ref' > run.l1o_tasks/fold_\$i/ref.fasta
        echo 'query' > run.l1o_tasks/fold_\$i/query.fasta
    done
    echo '{"wall_sec": 0.0, "returncode": 0, "timed_out": false, "max_rss_mb": 0.0}' > timing.json
    """
}
