"""Stand-alone TTS worker scripts. Each runs inside its own Python environment (the heavy models
have conflicting dependencies) and talks to ytauto over stdin/stdout, one JSON object per line."""
