DOMAIN = "edgedecision"
CONF_URL = "url"
CONF_FALLBACK = "fallback_agent"
CONF_MODEL = "model"
CONF_EXECUTE = "execute"
# Host name of the add-on inside Home Assistant = add-on slug with "_" -> "-". For an add-on installed from the
# GitHub repository the slug starts with the first 8 characters of sha1(repository URL in lower case):
#   https://github.com/lucapgt/edgedecision      -> a974f757
#   https://github.com/lucapgt/edgedecision/     -> 4c22f5ef
#   https://github.com/lucapgt/edgedecision.git  -> b7579572
# A local copy in /addons gets "local". The add-on is also looked up through the Supervisor (any *_edgedecision).
DEFAULT_URL = "http://a974f757-edgedecision:8765"
DEFAULT_FALLBACK = "conversation.home_assistant"
URL_CANDIDATES = [DEFAULT_URL, "http://4c22f5ef-edgedecision:8765", "http://b7579572-edgedecision:8765",
                  "http://local-edgedecision:8765", "http://127.0.0.1:8765", "http://localhost:8765"]
