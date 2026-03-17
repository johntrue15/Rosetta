# Mock XradiaPy for linting purposes
class XrmBasicDataSet:
    def ReadFile(self, path):
        pass
    
    def GetName(self):
        pass
    
    def IsInitializedCorrectly(self):
        pass
    
    def GetObjective(self):
        pass
    
    def GetPixelSize(self):
        pass
    
    def GetPower(self):
        pass
    
    def GetVoltage(self):
        pass
    
    def GetFilter(self):
        pass
    
    def GetBinning(self):
        pass
    
    def GetHeight(self):
        pass
    
    def GetWidth(self):
        pass
    
    def GetProjections(self):
        pass
    
    def GetAxesNames(self):
        pass
    
    def GetAxisPosition(self, idx, axis):
        pass
    
    def GetDate(self, idx):
        pass
    
    def GetDetectorToRADistance(self, idx):
        pass
    
    def GetSourceToRADistance(self, idx):
        pass
    
    def GetExposure(self, idx):
        pass

class Data:
    XRMData = type('XRMData', (), {'XrmBasicDataSet': XrmBasicDataSet}) 