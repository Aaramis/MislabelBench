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
    tuple val(meta), path(refjson), path(fasta), path(tax)

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
    """

    stub:
    """
    mkdir -p run.l1o_tasks
    echo '{"n_folds": 3}' > run.l1o_tasks/manifest.json
    echo 'model' > run.l1o_tasks/model
    for i in 000 001 002; do
        mkdir -p run.l1o_tasks/fold_\$i
        echo 'ref' > run.l1o_tasks/fold_\$i/ref.fasta
        echo 'query' > run.l1o_tasks/fold_\$i/query.fasta
    done
    echo '{"wall_sec": 0.0, "returncode": 0, "timed_out": false, "max_rss_mb": 0.0}' > timing.json
    touch stage.log
    """
}
