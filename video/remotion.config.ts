import {Config} from '@remotion/cli/config';

Config.setVideoImageFormat('jpeg');
Config.setOverwriteOutput(true);
// The laptop also runs the robot: keep rendering to a few cores.
Config.setConcurrency(4);
