"""Runtime feature flags for conservative rollout of optional capabilities."""

# Emergency safety default: keep visual-content analysis disabled on synchronous paths.
ENABLE_VISUAL_CONTENT_ANALYSIS = False

# Emergency safety default: keep face detection disabled unless explicitly requested.
ENABLE_FACE_DETECTION = False
