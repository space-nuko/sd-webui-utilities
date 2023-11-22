# LoRA Training command for sd-scripts, Oyasumi Ver.
# https://github.com/kohya-ss/sd-scripts
#
# Pass the training config CSV to use as an argument to the script:
# ./training_command.ps1 training_config.csv

# Config Start

# folder containing .ckpts/VAEs
$ckpt_dir = "E:\sd\models\Stable-diffusion";

# folder containing dataset folders, each one contains folders with repeats_conceptname ie: 12_A, 20_B, each subfolder contains images + text captions
$data_dir = "D:\stable-diffusion\training\lora\data";
# my_concepts_folder
#	12_A, images in A will repeat 12x
#	20_B, images in B will repeat 20x

#optional, just point this to an empty folder if you don't care.
$reg_dir = "D:\stable-diffusion\training\lora\reg";

# safetensors output folder
$output_dir = "D:\stable-diffusion\training\lora\out";

# logging directory
$logging_dir = "D:\stable-diffusion\training\lora\log";

# Config End

$run = Get-Content $args[0] | Select-String '^[^#]' | ConvertFrom-Csv
$total_batches = $run.Length

function Show-Notification {
    [cmdletbinding()]
    Param (
        [string]
        $ToastTitle,
        [string]
        [parameter(ValueFromPipeline)]
        $ToastText
    )

    [reflection.assembly]::loadwithpartialname('System.Windows.Forms')
    [reflection.assembly]::loadwithpartialname('System.Drawing')
    $notify = new-object system.windows.forms.notifyicon
    $notify.icon = [System.Drawing.SystemIcons]::Information
    $notify.visible = $true
    $notify.showballoontip(10,$ToastTitle,$ToastText,[system.windows.forms.tooltipicon]::None)
}

Clear-Host

$date = "{0:yyyy-MM-dd}" -f ([datetime]$(Get-Date).Ticks)

$ErrorActionPreference="SilentlyContinue"
Stop-Transcript | out-null
$ErrorActionPreference = "Stop"

Write-Output "Batches to run: $total_batches"

Write-Output "Validating config..."

$seen = @{}
$run | ForEach {
    Write-Output ""
    $id = $_.Id
    $dataset = $_.Dataset
    $ckpt = Join-Path -Path $ckpt_dir -ChildPath $_.Checkpoint
    $image_dir = Join-Path -Path $data_dir -ChildPath $dataset
    $output = Join-Path -Path $output_dir -ChildPath $date | Join-Path -ChildPath $id
    $vae = $_.VAE
    $keep_tokens = 0

    $extra = $_.ExtraOptions
    if ($extra -ne "" -And $extra -ne "None") {
        $extra = $extra.replace(";", ",") | ConvertFrom-Json -AsHashtable
        $keep_tokens = [int]($extra["keep_tokens"] ?? $keep_tokens)
        $extra.remove("keep_tokens")
        $noise_offset = [float]($extra["noise_offset"] ?? $noise_offset)
        $extra.remove("noise_offset")
        $use_lion_optimizer = [float]($extra["use_lion_optimizer"] ?? $false)
        $extra.remove("use_lion_optimizer")
        if ($extra.Count -gt 0) {
            Write-Error "Error: Invalid extra options: $extra"
        }
    }

    if ($seen.Contains($id)) {
        Write-Error "Error: Duplicate output ID: $id"
        Exit 1
    }

    $seen[$id] = $true

    if (!(Test-Path $ckpt)) {
        Write-Error "Error: Checkpoint file does not exist: $ckpt"
        Exit 1
    }
    if (![string]::IsNullOrWhiteSpace($vae)) {
        $vae = Join-Path -Path $ckpt_dir -ChildPath $vae
        if (!(Test-Path $vae)) {
            Write-Error "Error: VAE file does not exist: $vae"
            Exit 1
        }
    }
    if (!(Test-Path $image_dir)) {
        Write-Error "Error: Dataset path does not exist: $image_dir"
        Exit 1
    }
    if (Test-Path $output) {
        Write-Error "Error: Output path already exists: $output"
        Exit 1
    }

    $num_epochs = $_.NumEpochs
    $train_batch_size = $_.BatchSize
    $total = 0
    $folders = Get-ChildItem -Path $image_dir -Directory
    $folders | ForEach-Object {
        $parts, $rest = $_.Name -split "_", 2
        if($rest -eq $null)
        {
            Write-Error "Malformed directory: $($_.FullName)"
            Exit 1
        }
        $repeats = [int]$parts
        $imgs = Get-ChildItem $_.FullName -Recurse -File -Include *.png, *.bmp, *.gif, *.jpg,*.jpeg, *.webp | Measure-Object | ForEach-Object{$_.Count}
        $img_repeats = ($repeats * $imgs)
        Write-Output "`t$($repeats)_$($rest): $repeats repeats * $imgs images = $($img_repeats)"
        $total += $img_repeats
    }
    $mts = [int]($total / $train_batch_size * $num_epochs)
    Write-Output "${id}: Max training steps $total / $train_batch_size * $num_epochs = $mts"
    if ($mts -eq 0) {
        Write-Error "Error: Zero training steps for dataset: $image_dir"
        Exit 1
    }
}


Write-Host "Proceed? (Y/N)" -ForegroundColor Yellow -NoNewline
$confirmation = Read-Host
if ($confirmation -ne 'y') {
    Exit 1
}

$log_name = "lora_{0}.log" -f $(Get-Date).ToString("yyyy-MM-dd_HH-mm-ss")
$log_path = Join-Path -Path $output_dir -ChildPath $date | Join-Path -ChildPath $log_name
Start-Transcript -path $log_path -append

function Log-Message
{
    [CmdletBinding()]
    Param
    (
        [Parameter(Mandatory=$true, Position=0)]
        [string]$LogMessage
    )

    Write-Output ("{0} - {1}" -f (Get-Date), $LogMessage)
}

.\venv\Scripts\activate

$total_start_time = $(Get-Date)

$i = 1
$run | ForEach {
    $learning_rate = $_.LearningRate
    $unet_lr = $_.UNetLR
    $text_encoder_lr = $_.TextEncoderLR
    $train_batch_size = $_.BatchSize
    $num_epochs = $_.NumEpochs
    $save_every_n_epochs = $_.SaveEveryNEpochs
    $scheduler = $_.Scheduler
    $network_dim = $_.NetworkDimensions
    $network_alpha = $_.NetworkAlpha
    $keep_tokens = 0
    $noise_offset = 0.1
    $use_lion_optimizer = $false

    $extra = $_.ExtraOptions
    if ($extra -ne "" -And $extra -ne "None") {
        $extra = $extra.replace(";", ",") | ConvertFrom-Json -AsHashtable
        $keep_tokens = [int]($extra["keep_tokens"] ?? $keep_tokens)
        $noise_offset = [float]($extra["noise_offset"] ?? $noise_offset)
        $use_lion_optimizer = [bool]($extra["use_lion_optimizer"] ?? $use_lion_optimizer)
    }

    $id = $_.Id
    $dataset = $_.Dataset
    $ckpt = Join-Path -Path $ckpt_dir -ChildPath $_.Checkpoint
    $vae = ""
    if (![string]::IsNullOrWhiteSpace($_.VAE)) {
        $vae = Join-Path -Path $ckpt_dir -ChildPath $_.VAE
    }
    $image_dir = Join-Path -Path $data_dir -ChildPath $dataset
    $output = Join-Path -Path $output_dir -ChildPath $date | Join-Path -ChildPath $id

    $start_time = $(Get-Date)
    $start_time_s = $start_time.ToString("r")

    Write-Output "-------------------- Batch ${i} --------------------"
    Write-Output ""
    Write-Output $_
    Write-Output "*** Start Time: $start_time_s"
    Write-Output ""
    $i += 1

    Write-Output "Measuring folders:"
    $total = 0
    $folders = Get-ChildItem -Path $image_dir -Directory
    $folders | ForEach-Object {
        $parts, $rest = $_.Name -split "_", 2
        write-host $rest
        if($rest -eq $null)
        {
            Return
        }
        $repeats = [int]$parts
        $imgs = Get-ChildItem $_.FullName -Recurse -File -Include *.png, *.bmp, *.gif, *.jpg,*.jpeg, *.webp | Measure-Object | ForEach-Object{$_.Count}
        $img_repeats = ($repeats * $imgs)
        Write-Output "`t$($parts[1]): $repeats repeats * $imgs images = $($img_repeats)"
        $total += $img_repeats
    }
    Write-Output "Total images with repeats: $total"
    $mts = [int]($total / $train_batch_size * $num_epochs)
    Write-Output "Max training steps $total / $train_batch_size * $num_epochs = $mts"

    accelerate launch --num_cpu_threads_per_process 12 train_network.py `
        --network_module=networks.lora `
        --pretrained_model_name_or_path=$ckpt `
        --train_data_dir=$image_dir `
        --reg_data_dir=$reg_dir `
        --output_dir=$output `
        --caption_extension=".txt" `
        --shuffle_caption `
        <# --shuffle_caption #> `
        --keep_tokens=$keep_tokens `
        --prior_loss_weight=1 `
        --resolution=512 `
        --enable_bucket `
        --min_bucket_reso=256 `
        --max_bucket_reso=1024 `
        --train_batch_size=$train_batch_size `
        --learning_rate=$learning_rate `
        --unet_lr=$unet_lr `
        --text_encoder_lr=$text_encoder_lr `
        --max_train_steps=$mts `
        --mixed_precision="fp16" `
        --save_precision="fp16" `
        --use_8bit_adam `
        --xformers `
        --save_every_n_epochs=$save_every_n_epochs `
        --save_model_as=safetensors `
        --clip_skip=2 `
        --seed=23 `
        --network_dim=$network_dim `
        --network_alpha=$network_alpha `
        <# --color_aug #> `
        <# --flip_aug #> `
        --max_token_length=150 `
        --noise_offset=$noise_offset `
        --use_lion_optimizer=$use_lion_optimizer `
        --cache_latents `
        --persistent_data_loader_workers `
        --output_name=$id `
        --lr_scheduler=$scheduler `
        --logging_dir=$logging_dir `
        --vae=$vae ` # specifying the VAE is optional, do it if you want stuff to look normal with the VAE enabled #> `
        #--lr_warmup_steps=$lr_warmup_steps

    $end_time = $(Get-Date)
    $elapsed_time = $end_time - $start_time
    $total_time = "{0:HH:mm:ss}" -f ([datetime]$elapsed_time.Ticks)
    Write-Output ""
    Write-Output "*** Finished training at $end_time (elapsed: $total_time)"
    Write-Output ""

    Show-Notification "sd-scripts" "Finished training: $id (elapsed: $total_time)"
}

$end_time = $(Get-Date)
$end_time_s = $end_time.ToString("r")
$elapsed_time = $end_time - $total_start_time
$total_time = "{0:HH:mm:ss}" -f ([datetime]$elapsed_time.Ticks)
Write-Output "All training completed at $end_time_s"
Write-Output "Trained $total_batches batches in $total_time"

Stop-Transcript
