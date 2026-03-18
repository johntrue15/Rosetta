"""
Pytest configuration and fixtures for Rosetta tests.
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Add scripts directory to path for imports
REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def temp_dir():
    """Create a temporary directory that gets cleaned up after the test."""
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_pca_path():
    """Path to a sample PCA file in the repo (check data/tests/ first)."""
    # Check various possible locations (prefer data/tests/)
    candidates = [
        REPO_ROOT / "data" / "tests" / "Amazon echo 40 micron.pca",
        REPO_ROOT / "data" / "completed" / "Amazon echo 40 micron.pca",
        REPO_ROOT / "data" / "completed" / "Amazon echo 40 micron__moved_1.pca",
        REPO_ROOT / "data" / "Amazon echo 40 micron.pca",
    ]
    for path in candidates:
        if path.exists():
            return path
    # Return first candidate (will be skipped if not found)
    return candidates[0]


@pytest.fixture
def sample_rtf_path():
    """Path to a sample RTF file in the repo (check data/tests/ first)."""
    candidates = [
        REPO_ROOT / "data" / "tests" / "Technique-USNM35717_Stanley29.rtf",
        REPO_ROOT / "data" / "completed" / "Technique-USNM35717_Stanley.rtf",
        REPO_ROOT / "data" / "completed" / "Technique-USNM35717_Stanley29.rtf",
        REPO_ROOT / "data" / "Technique-USNM35717_Stanley.rtf",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


@pytest.fixture
def sample_xtekct_path():
    """Path to a sample XTEKCT file in the repo (check data/tests/ first)."""
    candidates = [
        REPO_ROOT / "data" / "tests" / "sample.xtekct",
        REPO_ROOT / "data" / "completed" / "JAG_Aip-lae-FMNH-213864-head_4I2E70EtOH_4wk.xtekct",
        REPO_ROOT / "data" / "JAG_Aip-lae-FMNH-213864-head_4I2E70EtOH_4wk.xtekct",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


@pytest.fixture
def mock_pca_content():
    """Minimal valid PCA file content for testing."""
    return """[General]
Version=2.8.2.20099
SystemName=v|tome|x m

[Geometry]
FDD=802.77534791
FOD=163.19250000
Magnification=4.91919266
VoxelSizeX=0.04065708
VoxelSizeY=0.04065708

[CT]
NumberImages=1800
ScanTimeCmpl=1800

[Xray]
Name=xs|240 d
Voltage=200
Current=200
Filter=0.1Cu

[Detector]
Name=DXR-250
Binning=0
TimingVal=333.096
Avg=4
Skip=1

[Image]
DimX=2024
DimY=2024

[CNC_0]
LoadPos=-149.993687
AcqPos=0.000000

[CNC_1]
LoadPos=394.998625
AcqPos=198.304750

[CNC_2]
LoadPos=273.987250
AcqPos=163.192500

[CNC_3]
AcqPos=0.000000

[CalibImages]
MGainPoints=3
Avg=100
Skip=10
MGainImg=S:\\CT_DATA\\FICS\\test\\calibration.tif
"""


@pytest.fixture
def mock_xtekct_content():
    """Minimal valid XTEKCT file content for testing."""
    return """[XTekCT]
Name=Test_Sample
VoxelsX=1150
VoxelSizeX=0.049751
VoxelsY=1939
VoxelSizeY=0.049751
Projections=2500
SrcToObject=183.012
SrcToDetector=735.7075
InitialAngle=0.0

[Xrays]
XraykV=216
XrayuA=229

[CTPro]
Filter_ThicknessMM=1.0
Filter_Material=Copper
"""


@pytest.fixture
def sample_skyscan_path():
    """Path to a sample SkyScan .log file in the repo (check data/tests/ first)."""
    candidates = [
        REPO_ROOT / "data" / "tests" / "cisco_70kv_450ua_3.9_w_IR_rec.log",
        REPO_ROOT / "data" / "completed" / "cisco_70kv_450ua_3.9_w_IR_rec.log",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


@pytest.fixture
def mock_skyscan_content():
    """Minimal valid Bruker SkyScan .log file content for testing."""
    return """[System]
Scanner=SkyScan2211
Instrument S/N=15A13010
Software=1.5.3
Source Type=Xray-Worx
Camera=FlatPanel Sensor
Camera Pixel Size (um)=74.800
[Acquisition]
Data directory=D:\\Data\\tanjid\\cisco\\cisco_sample_1
Filename prefix=cisco_70kv_450ua_3.9_w
Number of Files=  601
Source Voltage (kV)=  70
Source Current (uA)= 450
Source target type=Tungsten (W)
Number of Rows= 1536
Number of Columns= 3776
Image Pixel Size (um)=   40.00
Object to Source (mm)=151.006
Camera to Source (mm)=282.376
Camera binning=1x1
Exposure (ms)=   111
Filter=0.5 mm Al
Frame Averaging=ON (2)
Rotation Step (deg)=0.600
Use 360 Rotation=YES
Scan duration=0h:18m:3s
Study Date and Time=Dec 06, 2018  13:31:56
Image Rotation=-0.3610
Vertical Object Position (mm)=64.000
Scanning Trajectory=ROUND
Type Of Motion=STEP AND SHOOT
[Reconstruction]
Reconstruction Program=NRecon
Program Version=Version: 1.7.0.4
Reconstruction engine=InstaRecon
Pixel Size (um)=40.00000
Result File Type=TIF
Result Image Width (pixels)=3124
Result Image Height (pixels)=632
Ring Artifact Correction=14
Beam Hardening Correction (%)=51
Time and Date=Dec 14, 2018  16:03:20
[File name convention]
Filename Prefix=cisco_70kv_450ua_3.9_w_IR_rec
"""


@pytest.fixture
def mock_metadata_json():
    """Sample metadata.json content for testing aggregation and CSV conversion."""
    return [
        {
            "file_name": "test_sample.pca",
            "file_path": "S:\\CT_DATA\\FICS\\test_project\\data.pca",
            "ct_voxel_size_um": "40.65708",
            "xray_tube_voltage": "200",
            "xray_tube_current": "200",
            "xray_tube_power": "40.0",
            "ct_number_images": "1800",
            "sha256": "abc123",
            "source_path": "data/parsed/test_sample.pca.json",
        },
        {
            "file_name": "test_rtf.rtf",
            "file_path": "D:\\Nishimura\\USNM35685",
            "ct_voxel_size_um": "33.0",
            "xray_tube_voltage": "130",
            "xray_tube_current": "225",
            "xray_tube_power": "29.25",
            "ct_number_images": "3000",
            "sha256": "def456",
            "source_path": "data/parsed/test_rtf.rtf.json",
        },
    ]


@pytest.fixture
def mock_users_csv():
    """Sample users.csv content for testing user attribution."""
    return """Folder,User name,Email
FICS,John Doe,john.doe@example.com
Nishimura,Jane Smith,jane.smith@example.com
Stanley,Bob Wilson,bob.wilson@example.com
"""
