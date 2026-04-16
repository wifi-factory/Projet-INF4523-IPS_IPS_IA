param(
    [Parameter(Mandatory = $true)]
    [string]$InputMarkdownPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputDocxPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Add-NormalParagraph {
    param(
        $Document,
        [string]$Text
    )

    $paragraph = $Document.Paragraphs.Add()
    $paragraph.Range.Text = $Text
    $paragraph.Range.Style = "Normal"
    $paragraph.Range.InsertParagraphAfter() | Out-Null
}

function Add-HeadingParagraph {
    param(
        $Document,
        [string]$Text,
        [int]$Level
    )

    $paragraph = $Document.Paragraphs.Add()
    $paragraph.Range.Text = $Text
    $paragraph.Range.Style = "Heading $Level"
    $paragraph.Range.InsertParagraphAfter() | Out-Null
}

function Add-BulletParagraph {
    param(
        $Document,
        [string]$Text
    )

    $paragraph = $Document.Paragraphs.Add()
    $paragraph.Range.Text = $Text
    $paragraph.Range.Style = "Normal"
    $paragraph.Range.ListFormat.ApplyBulletDefault()
    $paragraph.Range.InsertParagraphAfter() | Out-Null
}

$inputPath = (Resolve-Path -LiteralPath $InputMarkdownPath).Path
$outputPath = [System.IO.Path]::GetFullPath($OutputDocxPath)
$outputDir = Split-Path -Parent $outputPath
if (-not (Test-Path -LiteralPath $outputDir)) {
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
}

$lines = Get-Content -LiteralPath $inputPath -Encoding UTF8

$word = $null
$document = $null

try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $document = $word.Documents.Add()

    foreach ($line in $lines) {
        if ($line -match '^\s*$') {
            continue
        }

        if ($line -match '^###\s+(.*)$') {
            Add-HeadingParagraph -Document $document -Text $Matches[1] -Level 3
            continue
        }

        if ($line -match '^##\s+(.*)$') {
            Add-HeadingParagraph -Document $document -Text $Matches[1] -Level 2
            continue
        }

        if ($line -match '^#\s+(.*)$') {
            Add-HeadingParagraph -Document $document -Text $Matches[1] -Level 1
            continue
        }

        if ($line -match '^\-\s+(.*)$') {
            Add-BulletParagraph -Document $document -Text $Matches[1]
            continue
        }

        Add-NormalParagraph -Document $document -Text $line
    }

    $wdFormatDocumentDefault = 16
    $document.SaveAs([ref]$outputPath, [ref]$wdFormatDocumentDefault)
}
finally {
    if ($document -ne $null) {
        $document.Close()
    }
    if ($word -ne $null) {
        $word.Quit()
    }
}

Write-Output "Generated DOCX: $outputPath"
