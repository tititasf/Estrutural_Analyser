import unittest
import os
import tempfile
from src.core.cad_utils import get_cad_version_info

class TestCADVersionExtractor(unittest.TestCase):
    def test_dwg_version_detection(self):
        # Mock a DWG file (AutoCAD 2018 is AC1032)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.dwg') as tmp:
            tmp.write(b'AC1032\x00\x00\x00')
            tmp_path = tmp.name
        
        try:
            version = get_cad_version_info(tmp_path)
            self.assertEqual(version, "AutoCAD 2018/2024")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_dxf_version_detection(self):
        # Mock a DXF file (AutoCAD 2013 is AC1027)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.dxf', mode='w') as tmp:
            tmp.write("0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1027\n0\nENDSEC")
            tmp_path = tmp.name
        
        try:
            version = get_cad_version_info(tmp_path)
            self.assertEqual(version, "AutoCAD 2013/2017")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_unknown_version(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix='.dwg') as tmp:
            tmp.write(b'AC9999')
            tmp_path = tmp.name
        
        try:
            version = get_cad_version_info(tmp_path)
            self.assertEqual(version, "Desconhecido")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

if __name__ == '__main__':
    unittest.main()
