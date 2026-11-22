import {Config} from '@remotion/cli/config';

// High-quality frames: JPEG at 95 keeps text and line art crisp (default 80 smears thin strokes).
Config.setVideoImageFormat('jpeg');
Config.setJpegQuality(95);
Config.setOverwriteOutput(true);
