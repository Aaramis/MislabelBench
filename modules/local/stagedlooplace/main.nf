// Stage 3 of 4, the only one that distributes: place one group of folds.
//
// The group is a stride, folds i, i+T, i+2T …, because that is the form the tool's -folds flag
// takes and it lets one invocation cover the whole group. One invocation per fold would be the
// worst available granularity: at eight threads the tool runs four placements of two threads each,
// so a fold costs 7.8 s in a group of 25 and 22.1 s alone. docs/distribution.md has the numbers.
//
// A task directory holding manifest.json, model and only this group's folds is enough -- checked
// by placing fold_007 from a 12 MB directory where the whole
// one is 284 MB. That is what keeps the staging cost proportional to the work.
process STAGEDLOOPLACE {
    tag "${meta.dataset}/${meta.condition}/rep${meta.rep} shard ${meta.shard}/${meta.n_shards}"
    label 'process_timed'

    conda "bioconda::sativa-epang=0.10.2"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/sativa-epang:0.10.2--py314hab16a5f_0' :
        'quay.io/biocontainers/sativa-epang:0.10.2--py314hab16a5f_0' }"

    input:
    tuple val(meta), path(manifest), path(model), path(folds, stageAs: 'folds/*')

    output:
    tuple val(meta), path("taskdir/fold_*"), emit: folds
    tuple val(meta), path("timing.json")   , emit: timing
    tuple val(meta), path("stage.log")     , emit: log

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    # Assembled rather than written into: the staged folds are symlinks into another task's
    # directory, and the tool writes its placements beside the inputs.
    mkdir -p taskdir
    cp ${manifest} taskdir/manifest.json
    cp ${model} taskdir/model
    for d in folds/fold_*; do
        mkdir -p taskdir/\$(basename \$d)
        cp -L \$d/* taskdir/\$(basename \$d)/
    done

    export SATIVA_L1O_ENGINE=${meta.engine}
    export OMP_NUM_THREADS=${meta.threads}

    _timeit.py --stdout stage.log -- \\
        sativa-epang -stage loo-place -taskdir \$PWD/taskdir \\
            -T ${meta.threads} -folds ${meta.shard}/${meta.n_shards} \\
        > timing.json

    # The tool does not fail when folds fail: an OOM-killed run logged "EPA-ng FAIL fold 18:" with
    # nothing after the colon, then "placed 7/12 folds", and carried on. Counting is independent
    # of it.
    want=\$(ls -d taskdir/fold_* | wc -l)
    got=\$(ls taskdir/fold_*/epa_result.jplace 2>/dev/null | wc -l)
    empty=\$(find taskdir -name epa_result.jplace -size 0 | wc -l)
    # -eq, not =: `wc -l` pads its output on some platforms and "       3" = "3" is false.
    [ "\$got" -eq "\$want" ] || { echo "placed \$got of \$want folds in this shard" >&2; exit 1; }
    [ "\$empty" -eq 0 ] || { echo "\$empty placements are empty" >&2; exit 1; }
    """

    stub:
    """
    mkdir -p taskdir
    for d in folds/fold_*; do
        n=\$(basename \$d)
        mkdir -p taskdir/\$n
        cp -L \$d/* taskdir/\$n/ 2>/dev/null || true
        echo '{"placements": []}' > taskdir/\$n/epa_result.jplace
    done
    echo '{"wall_sec": 0.0, "returncode": 0, "timed_out": false, "max_rss_mb": 0.0}' > timing.json
    touch stage.log
    """
}
