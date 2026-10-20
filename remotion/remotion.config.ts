import { Config } from "@remotion/cli/config";

// PNG frames keep the alpha channel. Lionstone passes codec flags per render:
// ProRes 4444 (transparent) for compositing, H.264 for previews.
Config.setVideoImageFormat("png");
Config.setConcurrency(null);
