from __future__ import annotations

# Elevation quantization in meters; smaller values increase precision but cost
# more memory and CPU when quantized.
ELEV_Q_M: float = 0.1

# Default planet radius in meters; changing this scales the entire world.
PLANET_RADIUS_M_DEFAULT: float = 6_371_000.0

# Default elevation smoothing passes; more passes soften terrain features.
ELEVATION_SMOOTH_PASSES_DEFAULT: int = 4
# Default target ocean fraction; higher values yield more ocean coverage.
ELEVATION_TARGET_OCEAN_FRAC_DEFAULT: float = 0.68
# Default smoothing strength; higher values blur elevation faster per pass.
ELEVATION_SMOOTH_STRENGTH_DEFAULT: float = 0.35
# Default smoothing cap in meters; higher values allow larger elevation shifts.
ELEVATION_SMOOTH_CAP_M_DEFAULT: float = 90.0
# Default erosion iterations; more iterations increase erosion effects.
ELEVATION_EROSION_ITERATIONS_DEFAULT: int = 2
# Default talus angle in degrees; higher angles reduce thermal erosion.
ELEVATION_TALUS_ANGLE_DEG_DEFAULT: float = 35.0

# Default equator temperature in Celsius; higher values warm the world.
CLIMATE_T_EQUATOR_DEFAULT: float = 30.0
# Default pole temperature in Celsius; lower values make poles colder.
CLIMATE_T_POLE_DEFAULT: float = -20.0
# Default lapse rate in C/km; higher values cool mountains faster.
CLIMATE_LAPSE_C_PER_KM_DEFAULT: float = 6.0
# Default latitude curve exponent; higher values concentrate extremes near poles.
CLIMATE_LAT_GAMMA_DEFAULT: float = 1.15
# Default polar cap cutoff (unit sphere z); larger values expand polar calm zones.
CLIMATE_LAT_POLAR_CAP_DEFAULT: float = 0.985
# Default advection steps; more steps transport moisture farther.
CLIMATE_ADVECT_STEPS_DEFAULT: int = 96
# Default wind transport fraction; higher values move more moisture per step.
CLIMATE_TRANSPORT_FRAC_DEFAULT: float = 0.85
# Default orographic scale in meters; higher values reduce orographic lift.
CLIMATE_OROG_SCALE_M_DEFAULT: float = 500.0

# Default minimum catchment size in cells; higher values reduce river count.
HYDROLOGY_MIN_CATCHMENT_CELLS_DEFAULT: int = 256
# Default log base for river intensity; higher values compress intensity range.
HYDROLOGY_INTENSITY_LOG_BASE_DEFAULT: float = 10.0

# Domain constants for deterministic hash streams; change only to decorrelate.
BIOME_JITTER_DOMAIN: int = 0x42494F4D
# Domain constant for noise seed separation; change to alter noise stream.
NOISE_DOMAIN: int = 0x4E4F4953
# Domain constant for tectonic plate seeding; change to decorrelate plates.
PLATE_SEED_DOMAIN: int = 0x504C4154
# Domain constant for wind direction jitter; change to decorrelate winds.
WIND_DOMAIN: int = 0x57494E44
# Domain constant for flow-direction hashing; change to decorrelate flow ties.
FLOW_DOMAIN: int = 0x464C4F57
# Domain constant for flat-region hashing; change to decorrelate flat ties.
FLAT_DOMAIN: int = 0x464C4154

# Mask for 64-bit hash arithmetic; change only if hash width changes.
HASH_MASK_64: int = 0xFFFFFFFFFFFFFFFF
# Mask for 32-bit hash arithmetic; change only if hash width changes.
HASH_MASK_32: int = 0xFFFFFFFF
# SplitMix64 increment constant; altering changes hash sequence.
HASH_SPLITMIX_INCREMENT: int = 0x9E3779B97F4A7C15
# SplitMix64 mix constant 1; altering changes hash distribution.
HASH_SPLITMIX_MUL1: int = 0xBF58476D1CE4E5B9
# SplitMix64 mix constant 2; altering changes hash distribution.
HASH_SPLITMIX_MUL2: int = 0x94D049BB133111EB

# Noise octave multiplier; changing shifts octave seed spacing.
NOISE_OCTAVE_CONST: int = 0x9E3779B9

# Flow direction unresolved sentinel; changing requires regeneration.
FLOW_UNRESOLVED: int = -2
# Flow direction sink sentinel; changing requires regeneration.
FLOW_SINK: int = -1
# Flow heap jitter mask; higher values increase tie-break entropy.
FLOW_HEAP_JITTER_MASK: int = 0xFFFF
# Flow heap jitter scale; higher values increase randomness in flow ties.
FLOW_HEAP_JITTER_SCALE: float = 1e-6

# Cube-sphere edge identifiers; changing swaps edge indexing conventions.
EDGE_NORTH: int = 0
# Cube-sphere edge identifiers; changing swaps edge indexing conventions.
EDGE_EAST: int = 1
# Cube-sphere edge identifiers; changing swaps edge indexing conventions.
EDGE_SOUTH: int = 2
# Cube-sphere edge identifiers; changing swaps edge indexing conventions.
EDGE_WEST: int = 3

# Normalization epsilon; higher values reduce sensitivity to flat fields.
NORMALIZE_EPS: float = 1e-8

# Wind reference threshold near poles; lower values expand pole handling.
WIND_POLE_REF_THRESHOLD: float = 0.99
# Wind band frequency for hemispheric sign; higher values add bands.
WIND_SIGN_LAT_FREQ: float = 3.0
# Wind score floor; more negative values reduce tie bias.
WIND_SCORE_FLOOR: float = -1.0e20
# Wind jitter mask; higher values increase tie-break entropy.
WIND_JITTER_MASK: int = 0xFFFF
# Wind jitter scale; higher values add more randomness to wind selection.
WIND_JITTER_SCALE: float = 1e-9

# Base tectonic noise octaves; more octaves add large-scale detail.
ELEVATION_BASE_NOISE_OCTAVES: int = 4
# Base tectonic noise lacunarity; higher values increase frequency growth.
ELEVATION_BASE_NOISE_LACUNARITY: float = 2.0
# Base tectonic noise persistence; higher values keep higher-octave energy.
ELEVATION_BASE_NOISE_PERSISTENCE: float = 0.5
# Base tectonic noise scale; higher values shrink features.
ELEVATION_BASE_NOISE_SCALE: float = 1.0

# Roughness noise octaves; more octaves add fine detail.
ELEVATION_ROUGH_NOISE_OCTAVES: int = 2
# Roughness noise lacunarity; higher values increase fine feature frequency.
ELEVATION_ROUGH_NOISE_LACUNARITY: float = 2.2
# Roughness noise persistence; higher values keep higher-octave energy.
ELEVATION_ROUGH_NOISE_PERSISTENCE: float = 0.6
# Roughness noise scale; higher values shrink roughness features.
ELEVATION_ROUGH_NOISE_SCALE: float = 3.0

# Plate noise octaves; more octaves add plate boundary texture.
ELEVATION_PLATE_NOISE_OCTAVES: int = 2
# Plate noise lacunarity; higher values increase plate boundary frequency.
ELEVATION_PLATE_NOISE_LACUNARITY: float = 2.0
# Plate noise persistence; higher values keep higher-octave energy.
ELEVATION_PLATE_NOISE_PERSISTENCE: float = 0.5
# Plate noise scale; higher values shrink plate features.
ELEVATION_PLATE_NOISE_SCALE: float = 0.5

# Tectonic mask exponent; higher values emphasize peaks.
ELEVATION_TECTONIC_EXPONENT: float = 1.25
# Plate mask exponent; higher values emphasize plate contrasts.
ELEVATION_PLATE_EXPONENT: float = 1.05
# Roughness mask exponent; higher values emphasize local noise.
ELEVATION_ROUGHNESS_EXPONENT: float = 1.6

# Tectonic amplitude in meters; higher values increase mountain height.
ELEVATION_TECTONIC_AMPLITUDE_M: float = 3500.0
# Plate amplitude in meters; higher values increase plate-driven relief.
ELEVATION_PLATE_AMPLITUDE_M: float = 1000.0
# Roughness amplitude in meters; higher values add small-scale variation.
ELEVATION_ROUGHNESS_AMPLITUDE_M: float = 700.0
# Roughness baseline; higher values bias terrain upward.
ELEVATION_ROUGHNESS_BASELINE: float = 0.5

# Hydraulic erosion coefficient; higher values erode faster per iteration.
ELEVATION_HYDRAULIC_K_DEFAULT: float = 0.01

# Initial moisture over ocean; higher values seed wetter climates.
CLIMATE_OCEAN_INIT_MOISTURE: float = 0.7
# Initial moisture over land; higher values seed wetter land climates.
CLIMATE_LAND_INIT_MOISTURE: float = 0.3
# Ocean moisture source floor; higher values keep oceans wetter.
CLIMATE_OCEAN_SOURCE_MOISTURE: float = 0.6
# Moisture capacity minimum; higher values increase baseline humidity.
CLIMATE_CAP_MIN: float = 0.05
# Moisture capacity slope; higher values increase humidity with temperature.
CLIMATE_CAP_SLOPE: float = 0.015
# Moisture capacity lower clamp; higher values prevent extreme drying.
CLIMATE_CAP_LO: float = 0.1
# Moisture capacity upper clamp; higher values allow more humid air.
CLIMATE_CAP_HI: float = 1.0

# Report sampling default; larger values reduce noise at higher cost.
REPORT_SAMPLE_SIZE_DEFAULT: int = 10000
# Report percentiles in whole percent; add/remove values to change output.
REPORT_PERCENTILES_PCT: tuple[int, ...] = (5, 25, 50, 75, 95)
# Report quantile fractions keyed by output name; change entries to adjust output.
REPORT_QUANTILES: dict[str, float] = {
    "p5": 0.05,
    "p25": 0.25,
    "p50": 0.5,
    "p75": 0.75,
    "p95": 0.95,
}
# Seam ratio epsilon; higher values reduce division instability.
REPORT_SEAM_EPS: float = 1e-8
