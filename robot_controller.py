def calculaAngulos():
        prism = 0
        th1 = 0
        th2 = 0
        th3 = 0
        th4 = 0

        return (prism,th1,th2,th3,th4)

class RobotController:

    def __init__(self, curr_px=None, curr_py=None, curr_pz=None, to_px=None, to_py=None, to_pz=None):
        self.Px_atual = curr_px
        self.Py_atual = curr_py
        self.Pz_atual = curr_pz
    
    def set_P_atual(self, px, py, pz):
        self.Px_atual = px
        self.Py_atual = py
        self.Pz_atual = pz
    
    def get_P_atual(self):
        return [self.Px_atual, self.Py_atual, self.Pz_atual]
    
    def set_desired_angles(self, desired_px, desired_py, desired_pz):
        angles = calculaAngulos()
        return angles


    

