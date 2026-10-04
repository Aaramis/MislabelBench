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
    # --dnaout because the model is RNA and the data DNA; --matchonly keeps the model's own
    # columns, so the alignment has a fixed width rather than one widened by every insertion
    # in every sequence.
    #
    # Pfam rather than AFA: cmalign refuses the interleaved formats above 10000 sequences or
    # 100000 residues, and the archaeal set is 7051 sequences but about 10 M residues. Pfam
    # is non-interleaved Stockholm, one sequence per line, so awk converts it to the fasta
    # SATIVA reads. Checked against AFA on a 50-sequence sample: byte identical.
    cmalign \\
        --cpu ${task.cpus} \\
        --dnaout \\
        --matchonly \\
        --outformat Pfam \\
        -o ${meta.id}.pfam \\
        --sfile ${meta.id}.cmalign.txt \\
        ${args} \\
        ${cm} \\
        ${fasta}

    awk '!/^#/ && !/^\\/\\// && NF==2 {print ">"\$1"\\n"\$2}' ${meta.id}.pfam \\
        > ${meta.id}.aligned.fasta

    # The converter keeps lines of exactly two fields, so a sequence whose name contained
    # whitespace would be dropped without a word and the alignment would simply be shorter than the
    # input. Nothing downstream would notice: SATIVA reads the alignment and the taxonomy
    # separately and reports a missing sequence as absent from the tree rather than as lost here.
    # The archaeal set has no such name -- 7051 in, 7051 out, checked against the committed files --
    # which is why this has never fired and why it is worth having before the next dataset.
    n_in=\$(grep -c '^>' ${fasta})
    n_out=\$(grep -c '^>' ${meta.id}.aligned.fasta)
    [ "\$n_in" = "\$n_out" ] || {
        echo "alignment lost sequences: \$n_in in, \$n_out out" >&2
        exit 1
    }

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
