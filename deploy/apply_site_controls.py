"""Maintain one generated server include; caller validates Nginx and rolls back."""
from pathlib import Path
import re
from site_controls import validate,nginx
from websites import page

MARKER='location ~ /\\. { deny all; }'

def prepare_config(text,include):
 directive='include '+str(include)+';'
 if directive in text:return text
 if MARKER not in text:raise ValueError('Managed Nginx layout differs. Operator must review this site before adding controls')
 return text.replace(MARKER,MARKER+'\n '+directive)

def apply(site,target,include,settings,domain,check,reload):
 settings=validate(settings,domain)
 for path in [site,target,include,include.parent]:
  if path.is_symlink():raise ValueError('Unsafe managed configuration path')
 include.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
 previous=include.read_bytes() if include.exists() else None
 original=target.read_text()
 prior_errors={}
 errors=site/'_panel-errors'
 if errors.is_symlink():raise ValueError('Unsafe error-page directory')
 errors.mkdir(exist_ok=True,mode=0o755)
 # Do not delete old error documents while an older validated config may reference them.
 for code,message in settings['errors'].items():
  file=errors/(code+'.html')
  if file.is_symlink():raise ValueError('Unsafe error document')
  prior_errors[file]=file.read_bytes() if file.exists() else None
  file.write_text(page('HTTP '+code,message));file.chmod(0o644)
 try:
  include.write_text(nginx(settings,domain));include.chmod(0o644)
  target.write_text(prepare_config(original,include))
  check();reload()
 except Exception:
  target.write_text(original)
  for file,content in prior_errors.items():
   if content is None:file.unlink(missing_ok=True)
   else:file.write_bytes(content)
  if previous is None:include.unlink(missing_ok=True)
  else:include.write_bytes(previous)
  # Revalidate and restore the previous running configuration after a reload failure.
  try:check();reload()
  except Exception:pass
  raise
