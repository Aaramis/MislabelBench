// Align the SSU set against a Rfam covariance model.
//
// A covariance model represents rRNA secondary structure, which a profile HMM does not. The
// alignment is not what this benchmark is about, so the point is to use the method a reviewer
// cannot argue with and move on. See assets/datasets.yml for the model and its checksum.
process ALIGNSSU {
    tag "${meta.id}"
    label 'process_high'

    conda "bioconda::infernal=1.1.5"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/infernal:1.1.5--pl5321h031d066_3' :
        'quay.io/biocontainers/infernal:1.1.5--pl5321h031d066_3' }"

    input:
    tuple val(meta), path(fasta)
    path cm

    output:
    tuple val(meta), path("${meta.id}.aligned.fasta"), emit: alignment
    tuple val(meta), path("${meta.id}.cmalign.txt")  , emit: report
    path "versions.yml"                              , emit: versions, topic: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    """
    # --outformat AFA writes aligned fasta, which is what SATIVA reads; --dnaout because the
    # model is RNA and the data is DNA; --matchonly keeps the model's own columns, so the
    # alignment is a fixed width rather than widened by every insertion in every sequence.
    # The Infernal container ships no Easel binaries, so this has to be one call.
    cmalign \\
        --cpu ${task.cpus} \\
        --dnaout \\
        --matchonly \\
        --outformat AFA \\
        -o ${meta.id}.aligned.fasta \\
        --sfile ${meta.id}.cmalign.txt \\
        ${args} \\
        ${cm} \\
        ${fasta}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        infernal: \$(cmalign -h | sed -n 's/^# INFERNAL \\([0-9.]*\\).*/\\1/p')
    END_VERSIONS
    """

    stub:
    """
    touch ${meta.id}.aligned.fasta ${meta.id}.cmalign.txt
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        infernal: \$(cmalign -h | sed -n 's/^# INFERNAL \\([0-9.]*\\).*/\\1/p')
    END_VERSIONS
    """
}
