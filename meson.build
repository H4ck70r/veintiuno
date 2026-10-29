project('veintiuno',
  version: '1.1.0',
  meson_version: '>= 0.62.0',
  license: 'GPL-3.0-or-later',
)

i18n = import('i18n')
gnome = import('gnome')
python = import('python')

app_id = 'io.github.H4ck70r.Veintiuno'
prefix = get_option('prefix')
pkgdatadir = prefix / get_option('datadir') / meson.project_name()
localedir = prefix / get_option('localedir')

subdir('data')
subdir('src')
subdir('po')

py = python.find_installation('python3')
test('engine', py, args: ['-m', 'unittest', 'discover', '-s', meson.project_source_root() / 'tests'])

gnome.post_install(
  gtk_update_icon_cache: true,
  update_desktop_database: true,
)
