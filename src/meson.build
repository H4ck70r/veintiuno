py = python.find_installation('python3')

conf = configuration_data()
conf.set('PYTHON', py.full_path())
conf.set('VERSION', meson.project_version())
conf.set('pkgdatadir', pkgdatadir)
conf.set('localedir', localedir)

configure_file(
  input: 'veintiuno.in',
  output: 'veintiuno',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)

install_subdir('veintiuno',
  install_dir: pkgdatadir,
  exclude_directories: ['__pycache__', 'engine/__pycache__', 'ui/__pycache__'],
)
