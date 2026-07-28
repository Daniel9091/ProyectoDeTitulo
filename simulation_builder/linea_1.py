"""
Linea 1 con exel del profesor
"""
import random
from objects.math3d import Vector3
from objects.modular_vehicle import ModularVehicle
from objects.passenger_id_generator import PassengerIdGenerator
from objects.station import Station
from systems.network import Network
from systems.continuous_train import ContinuousTrain
from systems.brain import Brain
from simulation.station_factory import TrackIdAllocator, create_station, connect_station_to_network
from telemetry.recorder import NullRecorder
from config.constants import TREE_DZ


# ─── PARÁMETROS ──────────────────────────────────────────────────────────────
# Edita estos valores para definir el escenario.

VM_CAPACITY = 6      # int — personas por VM (ej: 6)
DENSITY     = 1.0      # float 0.0–1.0 — fracción de slots ocupados al inicio (ej: 1.0 = 100%)
BELT_MARGIN = 150.0    # float — metros libres antes del primer y después del último árbol

# Coordenada Y y Z de todas las estaciones (dejar en 0.0 para red lineal estándar)
STATION_Y = 0.0
STATION_Z = 0.0
BELT_Z    = STATION_Z - TREE_DZ   # el carril siempre está TREE_DZ por debajo de las estaciones


# ── Posición X de cada estación (metros desde el origen) ─────────────────────
# Separación mínima recomendada: ~1000 m entre estaciones contiguas
X_S1 = 500.0   # San Pablo
X_S2 = 1500.0   # Neptuno
X_S3 = 2500.0   # Pajaritos
X_S4 = 3500.0   # Las Rejas
X_S5 = 4500.0   # Ecuador
X_S6 = 5500.0   # San Alberto Hurtado
X_S7 = 6500.0   # Universidad de Santiago
X_S8 = 7500.0   # Estación Central
X_S9 = 8500.0   # Unión Latinoamericana
X_S10 = 9500.0   # República
X_S11 = 10500.0   # Los Héroes
X_S12 = 11500.0   # Moneda
X_S13 = 12500.0   # U. de Chile
X_S14 = 13500.0   # Santa Lucía
X_S15 = 14500.0   # Universidad Católica
X_S16 = 15500.0   # Baquedano
X_S17 = 16500.0   # Salvador
X_S18 = 17500.0   # Manuel Montt
X_S19 = 18500.0   # Pedro de Valdivia
X_S20 = 19500.0   # Los Leones
X_S21 = 20500.0   # Tobalaba
X_S22 = 21500.0   # El Golf
X_S23 = 22500.0   # Alcántara
X_S24 = 23500.0   # Escuela Militar
X_S25 = 24500.0   # Manquehue
X_S26 = 25500.0   # Hernando de Magallanes
X_S27 = 26500.0   # Los Dominicos

# ── Probabilidades de destino por estación ───────────────────────────────────
# dict[int, float] — claves = station_id destino, valores suman 1.0
# No incluir la propia estación como destino

DEST_FROM_1 = {2: 0.0071, 3: 0.0184, 4: 0.0328, 5: 0.0113, 6: 0.0181, 7: 0.0286, 8: 0.0405, 9: 0.014, 10: 0.0262, 11: 0.0658, 12: 0.0672, 13: 0.137, 14: 0.0356, 15: 0.0177, 16: 0.0576, 17: 0.0221, 18: 0.027, 19: 0.0381, 20: 0.0647, 21: 0.1231, 22: 0.0138, 23: 0.0105, 24: 0.0356, 25: 0.0507, 26: 0.0092, 27: 0.0271}  # San Pablo
DEST_FROM_2 = {1: 0.0496, 3: 0.0176, 4: 0.0314, 5: 0.0108, 6: 0.0173, 7: 0.0273, 8: 0.0388, 9: 0.0134, 10: 0.0251, 11: 0.063, 12: 0.0643, 13: 0.1312, 14: 0.0341, 15: 0.017, 16: 0.0551, 17: 0.0211, 18: 0.0259, 19: 0.0365, 20: 0.0619, 21: 0.1179, 22: 0.0132, 23: 0.0101, 24: 0.0341, 25: 0.0486, 26: 0.0088, 27: 0.0259}  # Neptuno
DEST_FROM_3 = {1: 0.0501, 2: 0.0069, 4: 0.0318, 5: 0.011, 6: 0.0175, 7: 0.0276, 8: 0.0392, 9: 0.0135, 10: 0.0254, 11: 0.0637, 12: 0.065, 13: 0.1326, 14: 0.0345, 15: 0.0172, 16: 0.0557, 17: 0.0214, 18: 0.0262, 19: 0.0369, 20: 0.0626, 21: 0.1192, 22: 0.0134, 23: 0.0102, 24: 0.0344, 25: 0.0491, 26: 0.0089, 27: 0.0262}  # Pajaritos
DEST_FROM_4 = {1: 0.0508, 2: 0.007, 3: 0.0181, 5: 0.0111, 6: 0.0177, 7: 0.028, 8: 0.0398, 9: 0.0137, 10: 0.0257, 11: 0.0646, 12: 0.0659, 13: 0.1345, 14: 0.035, 15: 0.0174, 16: 0.0565, 17: 0.0217, 18: 0.0265, 19: 0.0374, 20: 0.0635, 21: 0.1208, 22: 0.0135, 23: 0.0103, 24: 0.0349, 25: 0.0498, 26: 0.009, 27: 0.0266}  # Las Rejas
DEST_FROM_5 = {1: 0.0498, 2: 0.0068, 3: 0.0177, 4: 0.0316, 6: 0.0174, 7: 0.0274, 8: 0.0389, 9: 0.0134, 10: 0.0252, 11: 0.0633, 12: 0.0646, 13: 0.1317, 14: 0.0342, 15: 0.017, 16: 0.0554, 17: 0.0212, 18: 0.026, 19: 0.0366, 20: 0.0622, 21: 0.1183, 22: 0.0133, 23: 0.0101, 24: 0.0342, 25: 0.0488, 26: 0.0089, 27: 0.026}  # Ecuador
DEST_FROM_6 = {1: 0.0501, 2: 0.0069, 3: 0.0178, 4: 0.0318, 5: 0.011, 7: 0.0276, 8: 0.0392, 9: 0.0135, 10: 0.0253, 11: 0.0637, 12: 0.065, 13: 0.1326, 14: 0.0345, 15: 0.0172, 16: 0.0557, 17: 0.0214, 18: 0.0262, 19: 0.0368, 20: 0.0626, 21: 0.1191, 22: 0.0134, 23: 0.0102, 24: 0.0344, 25: 0.0491, 26: 0.0089, 27: 0.0262}  # San Alberto Hurtado
DEST_FROM_7 = {1: 0.0506, 2: 0.007, 3: 0.018, 4: 0.0321, 5: 0.0111, 6: 0.0177, 8: 0.0396, 9: 0.0137, 10: 0.0256, 11: 0.0643, 12: 0.0656, 13: 0.1339, 14: 0.0348, 15: 0.0173, 16: 0.0563, 17: 0.0216, 18: 0.0264, 19: 0.0372, 20: 0.0632, 21: 0.1203, 22: 0.0135, 23: 0.0103, 24: 0.0348, 25: 0.0496, 26: 0.009, 27: 0.0265}  # Universidad de Santiago
DEST_FROM_8 = {1: 0.0512, 2: 0.007, 3: 0.0182, 4: 0.0325, 5: 0.0112, 6: 0.0179, 7: 0.0282, 9: 0.0138, 10: 0.0259, 11: 0.0651, 12: 0.0664, 13: 0.1355, 14: 0.0352, 15: 0.0175, 16: 0.0569, 17: 0.0218, 18: 0.0267, 19: 0.0377, 20: 0.064, 21: 0.1217, 22: 0.0136, 23: 0.0104, 24: 0.0352, 25: 0.0502, 26: 0.0091, 27: 0.0268}  # Estación Central
DEST_FROM_9 = {1: 0.0499, 2: 0.0069, 3: 0.0178, 4: 0.0316, 5: 0.0109, 6: 0.0174, 7: 0.0275, 8: 0.039, 10: 0.0252, 11: 0.0634, 12: 0.0647, 13: 0.132, 14: 0.0343, 15: 0.0171, 16: 0.0555, 17: 0.0213, 18: 0.026, 19: 0.0367, 20: 0.0623, 21: 0.1186, 22: 0.0133, 23: 0.0101, 24: 0.0343, 25: 0.0489, 26: 0.0089, 27: 0.0261}  # Unión Latinoamericana
DEST_FROM_10 = {1: 0.0505, 2: 0.0069, 3: 0.018, 4: 0.032, 5: 0.011, 6: 0.0176, 7: 0.0278, 8: 0.0395, 9: 0.0136, 11: 0.0642, 12: 0.0655, 13: 0.1336, 14: 0.0347, 15: 0.0173, 16: 0.0562, 17: 0.0215, 18: 0.0264, 19: 0.0371, 20: 0.0631, 21: 0.12, 22: 0.0135, 23: 0.0103, 24: 0.0347, 25: 0.0495, 26: 0.009, 27: 0.0264}  # República
DEST_FROM_11 = {1: 0.0525, 2: 0.0072, 3: 0.0187, 4: 0.0333, 5: 0.0115, 6: 0.0183, 7: 0.029, 8: 0.0411, 9: 0.0142, 10: 0.0266, 12: 0.0681, 13: 0.139, 14: 0.0361, 15: 0.018, 16: 0.0584, 17: 0.0224, 18: 0.0274, 19: 0.0386, 20: 0.0656, 21: 0.1249, 22: 0.014, 23: 0.0107, 24: 0.0361, 25: 0.0515, 26: 0.0093, 27: 0.0275}  # Los Héroes
DEST_FROM_12 = {1: 0.0526, 2: 0.0072, 3: 0.0187, 4: 0.0333, 5: 0.0115, 6: 0.0184, 7: 0.029, 8: 0.0411, 9: 0.0142, 10: 0.0266, 11: 0.0668, 13: 0.1392, 14: 0.0362, 15: 0.018, 16: 0.0585, 17: 0.0224, 18: 0.0275, 19: 0.0387, 20: 0.0657, 21: 0.125, 22: 0.014, 23: 0.0107, 24: 0.0361, 25: 0.0515, 26: 0.0094, 27: 0.0275}  # Moneda
DEST_FROM_13 = {1: 0.0566, 2: 0.0078, 3: 0.0202, 4: 0.0359, 5: 0.0124, 6: 0.0198, 7: 0.0312, 8: 0.0443, 9: 0.0153, 10: 0.0286, 11: 0.072, 12: 0.0734, 14: 0.0389, 15: 0.0194, 16: 0.063, 17: 0.0241, 18: 0.0296, 19: 0.0416, 20: 0.0707, 21: 0.1346, 22: 0.0151, 23: 0.0115, 24: 0.0389, 25: 0.0555, 26: 0.0101, 27: 0.0296}  # U. de Chile
DEST_FROM_14 = {1: 0.051, 2: 0.007, 3: 0.0182, 4: 0.0323, 5: 0.0111, 6: 0.0178, 7: 0.0281, 8: 0.0399, 9: 0.0138, 10: 0.0258, 11: 0.0648, 12: 0.0661, 13: 0.1349, 15: 0.0175, 16: 0.0567, 17: 0.0217, 18: 0.0266, 19: 0.0375, 20: 0.0637, 21: 0.1212, 22: 0.0136, 23: 0.0104, 24: 0.035, 25: 0.0499, 26: 0.0091, 27: 0.0267}  # Santa Lucía
DEST_FROM_15 = {1: 0.0501, 2: 0.0069, 3: 0.0178, 4: 0.0317, 5: 0.011, 6: 0.0175, 7: 0.0276, 8: 0.0392, 9: 0.0135, 10: 0.0253, 11: 0.0637, 12: 0.065, 13: 0.1325, 14: 0.0345, 16: 0.0557, 17: 0.0214, 18: 0.0261, 19: 0.0368, 20: 0.0626, 21: 0.1191, 22: 0.0133, 23: 0.0102, 24: 0.0344, 25: 0.0491, 26: 0.0089, 27: 0.0262}  # Universidad Católica
DEST_FROM_16 = {1: 0.0521, 2: 0.0072, 3: 0.0186, 4: 0.033, 5: 0.0114, 6: 0.0182, 7: 0.0287, 8: 0.0407, 9: 0.0141, 10: 0.0264, 11: 0.0662, 12: 0.0676, 13: 0.1378, 14: 0.0358, 15: 0.0178, 17: 0.0222, 18: 0.0272, 19: 0.0383, 20: 0.0651, 21: 0.1238, 22: 0.0139, 23: 0.0106, 24: 0.0358, 25: 0.051, 26: 0.0093, 27: 0.0273}  # Baquedano
DEST_FROM_17 = {1: 0.0503, 2: 0.0069, 3: 0.0179, 4: 0.0319, 5: 0.011, 6: 0.0176, 7: 0.0277, 8: 0.0393, 9: 0.0136, 10: 0.0254, 11: 0.0639, 12: 0.0652, 13: 0.1331, 14: 0.0346, 15: 0.0172, 16: 0.0559, 18: 0.0263, 19: 0.037, 20: 0.0628, 21: 0.1196, 22: 0.0134, 23: 0.0102, 24: 0.0345, 25: 0.0493, 26: 0.009, 27: 0.0263}  # Salvador
DEST_FROM_18 = {1: 0.0506, 2: 0.0069, 3: 0.018, 4: 0.032, 5: 0.0111, 6: 0.0176, 7: 0.0279, 8: 0.0395, 9: 0.0136, 10: 0.0256, 11: 0.0642, 12: 0.0655, 13: 0.1337, 14: 0.0348, 15: 0.0173, 16: 0.0562, 17: 0.0216, 19: 0.0372, 20: 0.0631, 21: 0.1201, 22: 0.0135, 23: 0.0103, 24: 0.0347, 25: 0.0495, 26: 0.009, 27: 0.0264}  # Manuel Montt
DEST_FROM_19 = {1: 0.0511, 2: 0.007, 3: 0.0182, 4: 0.0324, 5: 0.0112, 6: 0.0178, 7: 0.0282, 8: 0.04, 9: 0.0138, 10: 0.0259, 11: 0.0649, 12: 0.0663, 13: 0.1352, 14: 0.0351, 15: 0.0175, 16: 0.0568, 17: 0.0218, 18: 0.0267, 20: 0.0638, 21: 0.1215, 22: 0.0136, 23: 0.0104, 24: 0.0351, 25: 0.0501, 26: 0.0091, 27: 0.0267}  # Pedro de Valdivia
DEST_FROM_20 = {1: 0.0525, 2: 0.0072, 3: 0.0187, 4: 0.0333, 5: 0.0115, 6: 0.0183, 7: 0.0289, 8: 0.041, 9: 0.0142, 10: 0.0265, 11: 0.0667, 12: 0.068, 13: 0.1388, 14: 0.0361, 15: 0.018, 16: 0.0583, 17: 0.0224, 18: 0.0274, 19: 0.0386, 21: 0.1247, 22: 0.014, 23: 0.0107, 24: 0.036, 25: 0.0514, 26: 0.0093, 27: 0.0274}  # Los Leones
DEST_FROM_21 = {1: 0.0558, 2: 0.0077, 3: 0.0199, 4: 0.0354, 5: 0.0122, 6: 0.0195, 7: 0.0307, 8: 0.0436, 9: 0.015, 10: 0.0282, 11: 0.0709, 12: 0.0723, 13: 0.1476, 14: 0.0384, 15: 0.0191, 16: 0.062, 17: 0.0238, 18: 0.0291, 19: 0.041, 20: 0.0697, 22: 0.0149, 23: 0.0113, 24: 0.0383, 25: 0.0546, 26: 0.0099, 27: 0.0292}  # Tobalaba
DEST_FROM_22 = {1: 0.0499, 2: 0.0069, 3: 0.0178, 4: 0.0316, 5: 0.0109, 6: 0.0174, 7: 0.0275, 8: 0.039, 9: 0.0135, 10: 0.0252, 11: 0.0634, 12: 0.0647, 13: 0.132, 14: 0.0343, 15: 0.0171, 16: 0.0555, 17: 0.0213, 18: 0.026, 19: 0.0367, 20: 0.0623, 21: 0.1186, 23: 0.0101, 24: 0.0343, 25: 0.0489, 26: 0.0089, 27: 0.0261}  # El Golf
DEST_FROM_23 = {1: 0.0498, 2: 0.0068, 3: 0.0177, 4: 0.0315, 5: 0.0109, 6: 0.0174, 7: 0.0274, 8: 0.0389, 9: 0.0134, 10: 0.0252, 11: 0.0632, 12: 0.0645, 13: 0.1316, 14: 0.0342, 15: 0.017, 16: 0.0553, 17: 0.0212, 18: 0.026, 19: 0.0366, 20: 0.0621, 21: 0.1182, 22: 0.0133, 24: 0.0342, 25: 0.0487, 26: 0.0088, 27: 0.026}  # Alcántara
DEST_FROM_24 = {1: 0.051, 2: 0.007, 3: 0.0181, 4: 0.0323, 5: 0.0111, 6: 0.0178, 7: 0.0281, 8: 0.0399, 9: 0.0138, 10: 0.0258, 11: 0.0648, 12: 0.0661, 13: 0.1349, 14: 0.0351, 15: 0.0175, 16: 0.0567, 17: 0.0217, 18: 0.0266, 19: 0.0375, 20: 0.0637, 21: 0.1212, 22: 0.0136, 23: 0.0104, 25: 0.0499, 26: 0.0091, 27: 0.0267}  # Escuela Militar
DEST_FROM_25 = {1: 0.0518, 2: 0.0071, 3: 0.0184, 4: 0.0328, 5: 0.0113, 6: 0.0181, 7: 0.0285, 8: 0.0405, 9: 0.014, 10: 0.0262, 11: 0.0657, 12: 0.0671, 13: 0.1369, 14: 0.0356, 15: 0.0177, 16: 0.0575, 17: 0.0221, 18: 0.027, 19: 0.038, 20: 0.0646, 21: 0.123, 22: 0.0138, 23: 0.0105, 24: 0.0355, 26: 0.0092, 27: 0.0271}  # Manquehue
DEST_FROM_26 = {1: 0.0497, 2: 0.0068, 3: 0.0177, 4: 0.0315, 5: 0.0109, 6: 0.0173, 7: 0.0274, 8: 0.0389, 9: 0.0134, 10: 0.0251, 11: 0.0631, 12: 0.0644, 13: 0.1314, 14: 0.0342, 15: 0.017, 16: 0.0552, 17: 0.0212, 18: 0.0259, 19: 0.0365, 20: 0.062, 21: 0.1181, 22: 0.0132, 23: 0.0101, 24: 0.0341, 25: 0.0487, 27: 0.026}  # Hernando de Magallanes
DEST_FROM_27 = {1: 0.0506, 2: 0.0069, 3: 0.018, 4: 0.032, 5: 0.0111, 6: 0.0176, 7: 0.0279, 8: 0.0395, 9: 0.0136, 10: 0.0256, 11: 0.0642, 12: 0.0656, 13: 0.1337, 14: 0.0348, 15: 0.0173, 16: 0.0562, 17: 0.0215, 18: 0.0264, 19: 0.0372, 20: 0.0631, 21: 0.1202, 22: 0.0135, 23: 0.0103, 24: 0.0347, 25: 0.0495, 26: 0.009}  # Los Dominicos

# Agrega DEST_FROM_3, DEST_FROM_4, ...

# ── Tasas de generación ───────────────────────────────────────────────────────
# RATE = pasajeros/segundo que genera la estación
# VM_RATE = VMs/segundo que la estación solicita al sistema
# Regla de pulgar: VM_RATE = RATE / VM_CAPACITY (1 VM cuando se llenan los asientos)

RATE_S1    = 0.568681   # San Pablo
VM_RATE_S1 = RATE_S1 / VM_CAPACITY

RATE_S2    = 0.1563   # Neptuno
VM_RATE_S2 = RATE_S2 / VM_CAPACITY

RATE_S3    = 0.404856   # Pajaritos
VM_RATE_S3 = RATE_S3 / VM_CAPACITY

RATE_S4    = 0.720697   # Las Rejas
VM_RATE_S4 = RATE_S4 / VM_CAPACITY

RATE_S5    = 0.248567   # Ecuador
VM_RATE_S5 = RATE_S5 / VM_CAPACITY

RATE_S6    = 0.396689   # San Alberto Hurtado
VM_RATE_S6 = RATE_S6 / VM_CAPACITY

RATE_S7    = 0.626742   # Universidad de Santiago
VM_RATE_S7 = RATE_S7 / VM_CAPACITY

RATE_S8    = 0.889308   # Estación Central
VM_RATE_S8 = RATE_S8 / VM_CAPACITY

RATE_S9    = 0.306717   # Unión Latinoamericana
VM_RATE_S9 = RATE_S9 / VM_CAPACITY

RATE_S10    = 0.575228   # República
VM_RATE_S10 = RATE_S10 / VM_CAPACITY

RATE_S11    = 0.7224   # Los Héroes
VM_RATE_S11 = RATE_S11 / VM_CAPACITY

RATE_S12    = 1.474439   # Moneda
VM_RATE_S12 = RATE_S12 / VM_CAPACITY

RATE_S13    = 1.504092   # U. de Chile
VM_RATE_S13 = RATE_S13 / VM_CAPACITY

RATE_S14    = 0.782008   # Santa Lucía
VM_RATE_S14 = RATE_S14 / VM_CAPACITY

RATE_S15    = 0.389347   # Universidad Católica
VM_RATE_S15 = RATE_S15 / VM_CAPACITY

RATE_S16    = 0.632058   # Baquedano
VM_RATE_S16 = RATE_S16 / VM_CAPACITY

RATE_S17    = 0.484756   # Salvador
VM_RATE_S17 = RATE_S17 / VM_CAPACITY

RATE_S18    = 0.593414   # Manuel Montt
VM_RATE_S18 = RATE_S18 / VM_CAPACITY

RATE_S19    = 0.835983   # Pedro de Valdivia
VM_RATE_S19 = RATE_S19 / VM_CAPACITY

RATE_S20    = 0.709994   # Los Leones
VM_RATE_S20 = RATE_S20 / VM_CAPACITY

RATE_S21    = 1.351342   # Tobalaba
VM_RATE_S21 = RATE_S21 / VM_CAPACITY

RATE_S22    = 0.302956   # El Golf
VM_RATE_S22 = RATE_S22 / VM_CAPACITY

RATE_S23    = 0.231131   # Alcántara
VM_RATE_S23 = RATE_S23 / VM_CAPACITY

RATE_S24    = 0.780794   # Escuela Militar
VM_RATE_S24 = RATE_S24 / VM_CAPACITY

RATE_S25    = 1.113953   # Manquehue
VM_RATE_S25 = RATE_S25 / VM_CAPACITY

RATE_S26    = 0.202306   # Hernando de Magallanes
VM_RATE_S26 = RATE_S26 / VM_CAPACITY

RATE_S27    = 0.594744   # Los Dominicos
VM_RATE_S27 = RATE_S27 / VM_CAPACITY


# ─── BUILD ───────────────────────────────────────────────────────────────────

def build(seed: int = 42, recorder=None) -> tuple[Brain, dict[int, Station]]:
    """
    Construye el escenario.
    Retorna (brain, stations) listo para llamar brain.update(dt, current_time).
    """
    if recorder is None:
        recorder = NullRecorder()

    rng     = random.Random(seed)
    pid_gen = PassengerIdGenerator()
    alloc   = TrackIdAllocator(start=1)
    network = Network()
    stations: dict[int, Station] = {}

    # ── Estación 1 — San Pablo ───────────────────────────────────────
    s1, up1, l1, dn1, j_up_1, j_dn_1 = create_station(
        station_id=1,
        station_origin=Vector3(X_S1, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S1,
        destination_probabilities=DEST_FROM_1,
        vm_request_rate=VM_RATE_S1,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up1, l1, dn1, j_up_1, j_dn_1)
    stations[1] = s1

    # ── Estación 2 — Neptuno ─────────────────────────────────────────
    s2, up2, l2, dn2, j_up_2, j_dn_2 = create_station(
        station_id=2,
        station_origin=Vector3(X_S2, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S2,
        destination_probabilities=DEST_FROM_2,
        vm_request_rate=VM_RATE_S2,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up2, l2, dn2, j_up_2, j_dn_2)
    stations[2] = s2

    # ── Estación 3 — Pajaritos ───────────────────────────────────────
    s3, up3, l3, dn3, j_up_3, j_dn_3 = create_station(
        station_id=3,
        station_origin=Vector3(X_S3, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S3,
        destination_probabilities=DEST_FROM_3,
        vm_request_rate=VM_RATE_S3,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up3, l3, dn3, j_up_3, j_dn_3)
    stations[3] = s3

    # ── Estación 4 — Las Rejas ───────────────────────────────────────
    s4, up4, l4, dn4, j_up_4, j_dn_4 = create_station(
        station_id=4,
        station_origin=Vector3(X_S4, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S4,
        destination_probabilities=DEST_FROM_4,
        vm_request_rate=VM_RATE_S4,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up4, l4, dn4, j_up_4, j_dn_4)
    stations[4] = s4

    # ── Estación 5 — Ecuador ─────────────────────────────────────────
    s5, up5, l5, dn5, j_up_5, j_dn_5 = create_station(
        station_id=5,
        station_origin=Vector3(X_S5, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S5,
        destination_probabilities=DEST_FROM_5,
        vm_request_rate=VM_RATE_S5,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up5, l5, dn5, j_up_5, j_dn_5)
    stations[5] = s5

    # ── Estación 6 — San Alberto Hurtado ─────────────────────────────
    s6, up6, l6, dn6, j_up_6, j_dn_6 = create_station(
        station_id=6,
        station_origin=Vector3(X_S6, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S6,
        destination_probabilities=DEST_FROM_6,
        vm_request_rate=VM_RATE_S6,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up6, l6, dn6, j_up_6, j_dn_6)
    stations[6] = s6

    # ── Estación 7 — Universidad de Santiago ─────────────────────────
    s7, up7, l7, dn7, j_up_7, j_dn_7 = create_station(
        station_id=7,
        station_origin=Vector3(X_S7, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S7,
        destination_probabilities=DEST_FROM_7,
        vm_request_rate=VM_RATE_S7,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up7, l7, dn7, j_up_7, j_dn_7)
    stations[7] = s7

    # ── Estación 8 — Estación Central ────────────────────────────────
    s8, up8, l8, dn8, j_up_8, j_dn_8 = create_station(
        station_id=8,
        station_origin=Vector3(X_S8, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S8,
        destination_probabilities=DEST_FROM_8,
        vm_request_rate=VM_RATE_S8,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up8, l8, dn8, j_up_8, j_dn_8)
    stations[8] = s8

    # ── Estación 9 — Unión Latinoamericana ───────────────────────────
    s9, up9, l9, dn9, j_up_9, j_dn_9 = create_station(
        station_id=9,
        station_origin=Vector3(X_S9, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S9,
        destination_probabilities=DEST_FROM_9,
        vm_request_rate=VM_RATE_S9,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up9, l9, dn9, j_up_9, j_dn_9)
    stations[9] = s9

    # ── Estación 10 — República ───────────────────────────────────────
    s10, up10, l10, dn10, j_up_10, j_dn_10 = create_station(
        station_id=10,
        station_origin=Vector3(X_S10, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S10,
        destination_probabilities=DEST_FROM_10,
        vm_request_rate=VM_RATE_S10,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up10, l10, dn10, j_up_10, j_dn_10)
    stations[10] = s10

    # ── Estación 11 — Los Héroes ──────────────────────────────────────
    s11, up11, l11, dn11, j_up_11, j_dn_11 = create_station(
        station_id=11,
        station_origin=Vector3(X_S11, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S11,
        destination_probabilities=DEST_FROM_11,
        vm_request_rate=VM_RATE_S11,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up11, l11, dn11, j_up_11, j_dn_11)
    stations[11] = s11

    # ── Estación 12 — Moneda ──────────────────────────────────────────
    s12, up12, l12, dn12, j_up_12, j_dn_12 = create_station(
        station_id=12,
        station_origin=Vector3(X_S12, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S12,
        destination_probabilities=DEST_FROM_12,
        vm_request_rate=VM_RATE_S12,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up12, l12, dn12, j_up_12, j_dn_12)
    stations[12] = s12

    # ── Estación 13 — U. de Chile ─────────────────────────────────────
    s13, up13, l13, dn13, j_up_13, j_dn_13 = create_station(
        station_id=13,
        station_origin=Vector3(X_S13, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S13,
        destination_probabilities=DEST_FROM_13,
        vm_request_rate=VM_RATE_S13,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up13, l13, dn13, j_up_13, j_dn_13)
    stations[13] = s13

    # ── Estación 14 — Santa Lucía ─────────────────────────────────────
    s14, up14, l14, dn14, j_up_14, j_dn_14 = create_station(
        station_id=14,
        station_origin=Vector3(X_S14, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S14,
        destination_probabilities=DEST_FROM_14,
        vm_request_rate=VM_RATE_S14,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up14, l14, dn14, j_up_14, j_dn_14)
    stations[14] = s14

    # ── Estación 15 — Universidad Católica ────────────────────────────
    s15, up15, l15, dn15, j_up_15, j_dn_15 = create_station(
        station_id=15,
        station_origin=Vector3(X_S15, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S15,
        destination_probabilities=DEST_FROM_15,
        vm_request_rate=VM_RATE_S15,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up15, l15, dn15, j_up_15, j_dn_15)
    stations[15] = s15

    # ── Estación 16 — Baquedano ───────────────────────────────────────
    s16, up16, l16, dn16, j_up_16, j_dn_16 = create_station(
        station_id=16,
        station_origin=Vector3(X_S16, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S16,
        destination_probabilities=DEST_FROM_16,
        vm_request_rate=VM_RATE_S16,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up16, l16, dn16, j_up_16, j_dn_16)
    stations[16] = s16

    # ── Estación 17 — Salvador ────────────────────────────────────────
    s17, up17, l17, dn17, j_up_17, j_dn_17 = create_station(
        station_id=17,
        station_origin=Vector3(X_S17, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S17,
        destination_probabilities=DEST_FROM_17,
        vm_request_rate=VM_RATE_S17,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up17, l17, dn17, j_up_17, j_dn_17)
    stations[17] = s17

    # ── Estación 18 — Manuel Montt ────────────────────────────────────
    s18, up18, l18, dn18, j_up_18, j_dn_18 = create_station(
        station_id=18,
        station_origin=Vector3(X_S18, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S18,
        destination_probabilities=DEST_FROM_18,
        vm_request_rate=VM_RATE_S18,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up18, l18, dn18, j_up_18, j_dn_18)
    stations[18] = s18

    # ── Estación 19 — Pedro de Valdivia ───────────────────────────────
    s19, up19, l19, dn19, j_up_19, j_dn_19 = create_station(
        station_id=19,
        station_origin=Vector3(X_S19, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S19,
        destination_probabilities=DEST_FROM_19,
        vm_request_rate=VM_RATE_S19,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up19, l19, dn19, j_up_19, j_dn_19)
    stations[19] = s19

    # ── Estación 20 — Los Leones ──────────────────────────────────────
    s20, up20, l20, dn20, j_up_20, j_dn_20 = create_station(
        station_id=20,
        station_origin=Vector3(X_S20, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S20,
        destination_probabilities=DEST_FROM_20,
        vm_request_rate=VM_RATE_S20,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up20, l20, dn20, j_up_20, j_dn_20)
    stations[20] = s20

    # ── Estación 21 — Tobalaba ────────────────────────────────────────
    s21, up21, l21, dn21, j_up_21, j_dn_21 = create_station(
        station_id=21,
        station_origin=Vector3(X_S21, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S21,
        destination_probabilities=DEST_FROM_21,
        vm_request_rate=VM_RATE_S21,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up21, l21, dn21, j_up_21, j_dn_21)
    stations[21] = s21

    # ── Estación 22 — El Golf ─────────────────────────────────────────
    s22, up22, l22, dn22, j_up_22, j_dn_22 = create_station(
        station_id=22,
        station_origin=Vector3(X_S22, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S22,
        destination_probabilities=DEST_FROM_22,
        vm_request_rate=VM_RATE_S22,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up22, l22, dn22, j_up_22, j_dn_22)
    stations[22] = s22

    # ── Estación 23 — Alcántara ───────────────────────────────────────
    s23, up23, l23, dn23, j_up_23, j_dn_23 = create_station(
        station_id=23,
        station_origin=Vector3(X_S23, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S23,
        destination_probabilities=DEST_FROM_23,
        vm_request_rate=VM_RATE_S23,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up23, l23, dn23, j_up_23, j_dn_23)
    stations[23] = s23

    # ── Estación 24 — Escuela Militar ─────────────────────────────────
    s24, up24, l24, dn24, j_up_24, j_dn_24 = create_station(
        station_id=24,
        station_origin=Vector3(X_S24, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S24,
        destination_probabilities=DEST_FROM_24,
        vm_request_rate=VM_RATE_S24,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up24, l24, dn24, j_up_24, j_dn_24)
    stations[24] = s24

    # ── Estación 25 — Manquehue ───────────────────────────────────────
    s25, up25, l25, dn25, j_up_25, j_dn_25 = create_station(
        station_id=25,
        station_origin=Vector3(X_S25, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S25,
        destination_probabilities=DEST_FROM_25,
        vm_request_rate=VM_RATE_S25,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up25, l25, dn25, j_up_25, j_dn_25)
    stations[25] = s25

    # ── Estación 26 — Hernando de Magallanes ──────────────────────────
    s26, up26, l26, dn26, j_up_26, j_dn_26 = create_station(
        station_id=26,
        station_origin=Vector3(X_S26, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S26,
        destination_probabilities=DEST_FROM_26,
        vm_request_rate=VM_RATE_S26,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up26, l26, dn26, j_up_26, j_dn_26)
    stations[26] = s26

    # ── Estación 27 — Los Dominicos ───────────────────────────────────
    s27, up27, l27, dn27, j_up_27, j_dn_27 = create_station(
        station_id=27,
        station_origin=Vector3(X_S27, STATION_Y, STATION_Z),
        num_lanes=1,               # ajusta para esta estación
        passenger_rate=RATE_S27,
        destination_probabilities=DEST_FROM_27,
        vm_request_rate=VM_RATE_S27,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up27, l27, dn27, j_up_27, j_dn_27)
    stations[27] = s27

    # ── Belt ─────────────────────────────────────────────────────────────────
    # belt_end_x: toma el máximo de todos los j_dn_N.belt_x y agrega el margen
    belt_end_x = max(j_dn_1.belt_x, j_dn_2.belt_x, j_dn_3.belt_x, j_dn_4.belt_x, j_dn_5.belt_x, j_dn_6.belt_x, j_dn_7.belt_x, j_dn_8.belt_x, j_dn_9.belt_x, j_dn_10.belt_x, j_dn_11.belt_x, j_dn_12.belt_x, j_dn_13.belt_x, j_dn_14.belt_x, j_dn_15.belt_x, j_dn_16.belt_x, j_dn_17.belt_x, j_dn_18.belt_x, j_dn_19.belt_x, j_dn_20.belt_x, j_dn_21.belt_x, j_dn_22.belt_x, j_dn_23.belt_x, j_dn_24.belt_x, j_dn_25.belt_x, j_dn_26.belt_x, j_dn_27.belt_x) + BELT_MARGIN

    train = ContinuousTrain(
        start_pos  = Vector3(0.0, 0.0, BELT_Z),
        end_pos    = Vector3(belt_end_x, STATION_Y, BELT_Z),
        density    = DENSITY,
        vm_factory = lambda vm_id: ModularVehicle(vm_id, capacity=VM_CAPACITY),
        rng        = rng,
        junction_points = {
        1: j_up_1.belt_x,
        2: j_up_2.belt_x,
        3: j_up_3.belt_x,
        4: j_up_4.belt_x,
        5: j_up_5.belt_x,
        6: j_up_6.belt_x,
        7: j_up_7.belt_x,
        8: j_up_8.belt_x,
        9: j_up_9.belt_x,
        10: j_up_10.belt_x,
        11: j_up_11.belt_x,
        12: j_up_12.belt_x,
        13: j_up_13.belt_x,
        14: j_up_14.belt_x,
        15: j_up_15.belt_x,
        16: j_up_16.belt_x,
        17: j_up_17.belt_x,
        18: j_up_18.belt_x,
        19: j_up_19.belt_x,
        20: j_up_20.belt_x,
        21: j_up_21.belt_x,
        22: j_up_22.belt_x,
        23: j_up_23.belt_x,
        24: j_up_24.belt_x,
        25: j_up_25.belt_x,
        26: j_up_26.belt_x,
        27: j_up_27.belt_x,
        },
        recorder=recorder,
    )

    brain = Brain(train=train, network=network, stations=stations, recorder=recorder)
    return brain, stations