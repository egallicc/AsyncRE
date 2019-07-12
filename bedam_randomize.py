import sys
import math
import random
import sqlite3

class bedam_randomize:
#
# Utility functions to place ligand randomly in binding site
#
    def _center_of_mass(self,atoms):
        x_total = 0
        y_total = 0
        z_total = 0
        atom_count = 0
        for atom in atoms:
                x_total += atoms.get(atom)[0]
                y_total += atoms.get(atom)[1]
                z_total += atoms.get(atom)[2]
                atom_count += 1
        return ((x_total/atom_count),(y_total/atom_count),(z_total/atom_count))

    def _pick_points(self):
        # radius
        r = 1
        while True:
                # Latitude angle is random # between 0 - 360
                lat_angle = random.uniform(0,math.pi)
                # epsilon = cos(x)
                cosx = random.uniform(-1,1)
                # z coordinate
                z = r*cosx

                # sin(x) = +/- sqrt(1 - cos^2(x))
                sinx = math.sqrt(1 - math.pow(cosx,2))
                # Randomly choose -1 or 1 for the +/- part of previous equation
                seq = [-1,1]
                sign = random.choice(seq)
                sinx = sign * sinx

                # formulas for x & y coordinates
                y = r * sinx * math.sin(lat_angle)
                x = r * sinx * math.cos(lat_angle)

                if (math.pow(x,2) + math.pow(y,2) + math.pow(z,2) == 1):
                        break
        return(x,y,z)

# x is the angle
    def _rotate(self,atoms,center_mass_lig):
        atom_prime = atoms

        ux, uy, uz = self._pick_points()
        # x is theta
        x = random.uniform(0,2*math.pi)
        # rotation matrix
        R = [[(math.cos(x) + (ux**2 * (1 - math.cos(x)))),   (ux*uy * (1 - math.cos(x)) - (uz * math.sin(x))), 
              ((ux*uz * (1 - math.cos(x))) + uy*math.sin(x))],
             [((uy*ux * (1 - math.cos(x))) + uz*math.sin(x)), (math.cos(x) + ((uy**2) * (1 - math.cos(x)))), 
              ((uy*uz * (1 - math.cos(x))) - (ux * math.sin(x)))],
             [((uz*ux * (1 - math.cos(x))) - (uy * math.sin(x))), ((uz*uy * (1 - math.cos(x))) + (ux * math.sin(x))), 
              (math.cos(x) + (uz**2 * (1 - math.cos(x))))]]  

        # subtract center of mass from every atom
        for at in atom_prime.keys():
            atom_prime[at][0] -= center_mass_lig[0]
            atom_prime[at][1] -= center_mass_lig[1]
            atom_prime[at][2] -= center_mass_lig[2]

        for at in atom_prime.keys():
            atom_prime[at] = self._multiply(R,atom_prime[at])

        return atom_prime

    def _multiply(self,rotation_matrix,coordinates):
        atom_prime = [0,0,0]
        atom_prime[0] = (rotation_matrix[0][0] * coordinates[0]) + (rotation_matrix[0][1] * coordinates[1]) +  (rotation_matrix[0][2] * coordinates[2])
        atom_prime[1] = (rotation_matrix[1][0] * coordinates[0]) + (rotation_matrix[1][1] * coordinates[1]) +  (rotation_matrix[1][2] * coordinates[2])
        atom_prime[2] = (rotation_matrix[2][0] * coordinates[0]) + (rotation_matrix[2][1] * coordinates[1]) +  (rotation_matrix[2][2] * coordinates[2])
        return (atom_prime[0],atom_prime[1],atom_prime[2])
    

    def _add(self,translate_coordinates,coordinates):
        atom_prime = [0,0,0]
        atom_prime[0] = translate_coordinates[0] + coordinates[0]
        atom_prime[1] = translate_coordinates[1] + coordinates[1]
        atom_prime[2] = translate_coordinates[2] + coordinates[2]
        return (atom_prime[0],atom_prime[1],atom_prime[2])

    def _translate(self, atoms, center, r):
        # start with (0,0,0) to test this
        # radius in Angstroms
        # create a cube around the receptor
        #cube = [(0,0,0), (1,0,0), (1,1,0), (0,1,0), (0,0,1), (1,0,1), (1,1,1), (0,1,1)]

        atom_prime = atoms

        # Generate a random point within the cube and check if it's in the sphere
        # http://stackoverflow.com/questions/5531827/random-point-on-a-given-sphere
        # http://www.gamedev.net/topic/95637-random-point-within-a-sphere/
        while True:
                x = random.uniform(-r,r)
                y = random.uniform(-r,r)
                z = random.uniform(-r,r)
                if (x**2 + y**2 + z**2 > r**2):
                        break
        x += center[0]
        y += center[1]
        z += center[2]

        for at in atom_prime.keys():
            atom_prime[at] = self._add((x,y,z),atom_prime[at])

        return atom_prime


    def _place_ligand_randomly(self, ligand_atoms, center_mass_lig, center_mass_rcpt, radius):
        # returns modified ligand atom positions, so that the ligand CM is
        # at the receptor CM and oriented randomly
        #  ligand_atoms = dictionary of [x,y,z] positions, key is atom index
        #  ligand_cm, receptor_cm = [x,y,z] 
        
        # Rotate and translate the ligand randomly and translate
        rotated = self._rotate(ligand_atoms, center_mass_lig)
        new = self._translate(rotated,center_mass_rcpt,radius)
        
        return new

    def randomize_ligand_dms(self,rcptdms, ligdms, receptor_sql, ligand_sql, radius):
        # modify ligand dms file so that it is randomly oriented and placed within
        # binding site volume
        #  rcptdms = dms file of receptor
        #  ligdms = dms file of ligand
        #  receptor_sql, ligand_sql = sql selections of CM atoms
        #  radius = radius of binding site

        # key = atom id; value = list of (x,y,z) coordinates
        lig_atoms = {}
        lig_atoms_cm = {}
        rcpt_atoms_cm = {}

        # connect to dms databases
        rcpt_conn = sqlite3.connect(rcptdms)
        lig_conn = sqlite3.connect(ligdms)

        c_rcpt = rcpt_conn.cursor()
        c_lig = lig_conn.cursor()

        # get the atoms of the ligand
        c_lig.execute('SELECT id, x, y, z FROM particle')
        lig = c_lig.fetchall()
        for atom in lig:
            lig_atoms[atom[0]] = [atom[1],atom[2],atom[3]]

        # get the CM atoms of the ligand
        c_lig.execute('SELECT id, x, y, z FROM particle WHERE ' + ligand_sql)
        lig = c_lig.fetchall()
        for atom in lig:
            lig_atoms_cm[atom[0]] = [atom[1],atom[2],atom[3]]

        # get the CM atoms of the receptor
        c_rcpt.execute('SELECT id, x, y, z FROM particle WHERE ' + receptor_sql)
        rcpt = c_rcpt.fetchall()
        for atom in rcpt:
            rcpt_atoms_cm[atom[0]] = [atom[1],atom[2],atom[3]]
        
        # find the centers of mass
        center_mass_lig = self._center_of_mass(lig_atoms_cm)
        center_mass_rcpt = self._center_of_mass(rcpt_atoms_cm)

        # Rotate/translate the ligand randomly
        new_lig_atoms = self._place_ligand_randomly(lig_atoms, center_mass_lig, center_mass_rcpt, radius)

        # Update the coordinate values
        for idat in new_lig_atoms.keys():
            x = new_lig_atoms[idat][0]
            y = new_lig_atoms[idat][1]
            z = new_lig_atoms[idat][2]
            c_lig.execute('UPDATE particle SET x = {0}, y = {1}, z = {2} WHERE id = {3}'.format(x,y,z,idat))
        lig_conn.commit()
        
        lig_conn.close()
        rcpt_conn.close()

if __name__ == '__main__':

    if len(sys.argv) != 3:
        print "Usage: python bedam_randomize.py <rcptdms> <ligdms>"
        sys.exit(1)

    rcptdms = sys.argv[1]
    ligdms = sys.argv[2]

    rt = bedam_randomize()
    
    rt.keywords = {}
    rt.keywords['REST_LIGAND_CMTOL'] = 1.0
    rt.keywords['REST_LIGAND_CMRECSQL'] = "name GLOB 'O*'"
    rt.keywords['REST_LIGAND_CMLIGSQL'] = "anum > 1"
    
    rt.randomize_ligand_dms(rcptdms, ligdms)
