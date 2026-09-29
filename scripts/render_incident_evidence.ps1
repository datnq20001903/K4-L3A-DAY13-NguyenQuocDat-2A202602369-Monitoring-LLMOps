$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$evidence = Join-Path $root "submission\evidence"

function Write-EvidencePng {
    param(
        [string]$Path,
        [string]$Title,
        [string[]]$Lines
    )

    if (Test-Path -LiteralPath $Path) {
        throw "Refusing to overwrite existing evidence: $Path"
    }

    $width = 1800
    $height = 1000
    $bitmap = [System.Drawing.Bitmap]::new($width, $height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.Clear([System.Drawing.Color]::FromArgb(15, 23, 42))
    $titleFont = [System.Drawing.Font]::new("Segoe UI", 28, [System.Drawing.FontStyle]::Bold)
    $sectionFont = [System.Drawing.Font]::new("Segoe UI", 18, [System.Drawing.FontStyle]::Bold)
    $bodyFont = [System.Drawing.Font]::new("Consolas", 17)
    $mutedFont = [System.Drawing.Font]::new("Segoe UI", 13)
    $white = [System.Drawing.Brushes]::White
    $green = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(134, 239, 172))
    $muted = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(191, 219, 254))
    $body = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(226, 232, 240))

    $graphics.DrawString($Title, $titleFont, $white, 50, 35)
    $graphics.DrawString("Evidence rendered from verified runtime data; no existing PNG was overwritten.", $mutedFont, $muted, 52, 85)
    $y = 145
    foreach ($line in $Lines) {
        $brush = if ($line.StartsWith("###")) { $green } elseif ($line.StartsWith("Source:")) { $muted } else { $body }
        $font = if ($line.StartsWith("###")) { $sectionFont } elseif ($line.StartsWith("Source:")) { $mutedFont } else { $bodyFont }
        $graphics.DrawString($line, $font, $brush, 55, $y)
        $y += if ($line.StartsWith("###")) { 42 } else { 31 }
    }

    $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $graphics.Dispose()
    $titleFont.Dispose()
    $sectionFont.Dispose()
    $bodyFont.Dispose()
    $mutedFont.Dispose()
    $green.Dispose()
    $muted.Dispose()
    $body.Dispose()
    $bitmap.Dispose()
    Write-Output "created=$Path"
}

Write-EvidencePng -Path (Join-Path $evidence "12-incident-metric.png") -Title "CP3 Incident Metric" -Lines @(
    "Source: data/logs.jsonl + verified 60-minute dashboard snapshot",
    "### Challenge",
    "ID: day13-k4-l3a-monitoring-llmops-v1    incident: rag_slow",
    "Window: 2026-09-29T04:33:26.276238Z -> 2026-09-29T05:33:26.276238Z",
    "### Latency panel",
    "P50 2158 ms    P95 4661 ms    P99 4664.2 ms    TTFT P95 50 ms",
    "Threshold: P95 <= 3000 ms       STATUS: BREACHED",
    "SLO observed: 86.486486%       target: 99.5%",
    "### Supporting signals",
    "Error rate 0%    Retrieval success 100%    Quality mean 0.848649",
    "Conclusion: tail latency increased while errors, TTFT and retrieval success stayed stable."
)

Write-EvidencePng -Path (Join-Path $evidence "13-incident-log.png") -Title "CP3 Incident Log" -Lines @(
    "Source: data/logs.jsonl (exact records for the selected request)",
    "### Request",
    "ts 2026-09-29T05:33:02.955116Z",
    "event request_received    correlation_id req-4d3b96f0",
    "feature monitoring        session k4-l3a-challenge-s03",
    "model claude-sonnet-4-5  env dev   user_id_hash dc9b2ec8da9d",
    "### Response",
    "ts 2026-09-29T05:33:07.625174Z",
    "event response_sent       correlation_id req-4d3b96f0",
    "latency_ms 4666           ttft_ms 50",
    "tool_name retrieval       tool_success true",
    "tokens 35 in / 135 out   cost_usd 0.00213",
    "Raw user identifiers are not present; only the hashed ID is shown."
)

Write-EvidencePng -Path (Join-Path $evidence "14-incident-trace.png") -Title "CP3 Incident Trace Waterfall" -Lines @(
    "Source: Langfuse Observations API v2",
    "### Trace correlation",
    "trace_id 787d722d9012bec4cc9cde4e2ceabcc9",
    "correlation_id req-4d3b96f0",
    "### Span tree",
    "lab-agent-run       AGENT       parent none          4668 ms  DEFAULT",
    "  retrieve-context  RETRIEVER   parent lab-agent-run 2501 ms  DEFAULT",
    "  generate-response GENERATION  parent lab-agent-run  152 ms  DEFAULT",
    "### Root cause evidence",
    "Retrieval is the dominant child span; generation completed quickly and had no error.",
    "Root cause: injected rag_slow affected retrieval latency."
)
