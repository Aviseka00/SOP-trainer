import json
from pathlib import Path
import torch
import torchvision
import torchaudio
import gfpgan
import facexlib
import safetensors
import face_alignment
import librosa
import cv2

ROOT = Path(__file__).resolve().parent.parent
cuda = torch.cuda.is_available()
if cuda:
    torch.ones(2, device='cuda').sum().item()
result = {'torch':torch.__version__, 'torchvision':torchvision.__version__, 'cuda_available':cuda,
          'gpu':torch.cuda.get_device_name(0) if cuda else None, 'basic_cuda_operation_test':'passed' if cuda else 'not available'}
folder = ROOT/'models'/'sadtalker'
folder.mkdir(parents=True, exist_ok=True)
(folder/'runtime.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
