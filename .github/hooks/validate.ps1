param(
    [string]$Prompt
)

Write-Host "Validating user prompt..."

if ([string]::IsNullOrWhiteSpace($Prompt)) {
    Write-Host "BLOCK: Empty prompt."
    exit 1
}

# Simple safety/quality validation
$blockedWords = @(
    "delete_mission_log",
    "drop_database",
    "rm -rf"
)

foreach ($word in $blockedWords) {
    if ($Prompt -match [regex]::Escape($word)) {
        Write-Host "BLOCK: Prompt contains restricted operation: $word"
        exit 1
    }
}

Write-Host "PASS: Prompt validation successful."
exit 0