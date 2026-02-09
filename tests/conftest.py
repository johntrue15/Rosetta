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
    """Path to a sample PCA file in the repo."""
    return REPO_ROOT / "data" / "completed" / "Amazon echo 40 micron.pca"


@pytest.fixture
def sample_rtf_path():
    """Path to a sample RTF file in the repo."""
    # Check for RTF in data folder first, then completed
    rtf_in_data = REPO_ROOT / "data" / "Technique-USNM35717_COPY3.rtf"
    if rtf_in_data.exists():
        return rtf_in_data
    return REPO_ROOT / "data" / "completed" / "Technique-USNM35717_Stanley.rtf"


@pytest.fixture
def sample_xtekct_path():
    """Path to a sample XTEKCT file in the repo."""
    # Check for xtekct in data folder first, then completed
    xtekct_in_data = REPO_ROOT / "data" / "JAG_Aip-lae-FMNH-213864-head_4I2E70EtOH_4wk.xtekct"
    if xtekct_in_data.exists():
        return xtekct_in_data
    return REPO_ROOT / "data" / "completed" / "JAG_Aip-lae-FMNH-213864-head_4I2E70EtOH_4wk.xtekct"


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
