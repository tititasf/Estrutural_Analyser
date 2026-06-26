import aspose.cad as cad
import aspose.cad.imageoptions as imageoptions
import logging

def discover_options():
    print("--- DxfOptions ---")
    dxf_opts = imageoptions.DxfOptions()
    print(f"Attributes: {dir(dxf_opts)}")
    
    # Check for version-like attributes or enums in parent module
    print("\n--- cad.fileformats.cad.CadHeader --- (Common for versioning)")
    try:
        from aspose.cad.fileformats.cad import CadHeader
        print(f"CadHeader attributes: {dir(CadHeader)}")
    except:
        print("Could not import CadHeader")

    print("\n--- Searching for Version Enums ---")
    for attr in dir(cad):
        if "Version" in attr or "Format" in attr:
            print(f"Found something interesting in cad: {attr}")

    # For Aspose.CAD, often the version is in CadRasterizationOptions or specific to DxfOptions
    # Let's try to see if there is any 'AcadVersion' enum
    try:
        from aspose.cad import AcadVersion
        print(f"AcadVersion members: {dir(AcadVersion)}")
    except:
        print("AcadVersion not found directly in aspose.cad")

    try:
        # Check standard image options
        for attr in dir(imageoptions):
            if "Options" in attr:
                print(f"Option class available: {attr}")
    except:
        pass

discover_options()
