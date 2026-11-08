from pathlib import Path
import sys,os,subprocess,shutil,json
import hashlib
root=Path(__file__).parent
cc,cxx,ar,idf,target,config=sys.argv[1:7]
env=os.environ.copy()
python=Path(sys.executable).as_posix()
inputs=[root/'idf_include_flags.txt',Path(config)/'sdkconfig.h',root/'colcon.meta',Path(__file__)]
inputs+=list((root.parent.parent/'extra_ros_packages').rglob('*'))
signature=hashlib.sha256(b''.join(p.read_bytes() for p in inputs if p.is_file())).hexdigest()
stamp=root/'native-library-signature.txt'
if stamp.exists() and stamp.read_text()==signature and (root/'libmicroros.a').exists():
 print('MICROROS_NATIVE_LIBRARY_UP_TO_DATE',flush=True)
 sys.exit(0)

def run(args,cwd):
 print('BUILD_STAGE:',cwd.name,flush=True)
 if cwd.name=='micro_ros_src':
  args[args.index('--build-base')+1]='build-c'
  args[args.index('--install-base')+1]='install-c'
  args[args.index('--cmake-args'):args.index('--cmake-args')]=['--cmake-force-configure','--packages-ignore-regex=.*_cpp']
 subprocess.run(args,cwd=cwd,env=env,check=True)

dev=root/'micro_ros_dev';prefix=dev/'install-native'
if not (prefix/'.complete').exists():
 run([python,'-m','colcon','build','--merge-install','--build-base','build-native','--install-base','install-native','--packages-ignore','ament_index_cpp','gtest_vendor','gmock_vendor','--cmake-args','-G','Ninja','-DCMAKE_MAKE_PROGRAM=C:/Espressif/tools/ninja/1.12.1/ninja.exe','-DBUILD_TESTING=OFF','-DPython3_EXECUTABLE='+python],dev)
 (prefix/'.complete').touch()
# The host generator dependencies are Python/CMake tools, not target firmware.
env['AMENT_PREFIX_PATH']=str(prefix)
env['CMAKE_PREFIX_PATH']=str(prefix)
site=[p for p in prefix.rglob('site-packages') if p.is_dir()]
env['PYTHONPATH']=os.pathsep.join(map(str,site))+os.pathsep+env.get('PYTHONPATH','')
mcu=root/'micro_ros_src'
extra=root.parent.parent/'extra_ros_packages'
shutil.copytree(extra,mcu/'src/extra_packages',dirs_exist_ok=True)
for rel in ['rcl/rcl_yaml_param_parser','rcl_logging/rcl_logging_log4cxx','rcl_logging/rcl_logging_spdlog','rclc/rclc_examples','rosidl/rosidl_typesupport_introspection_cpp']:
 p=mcu/'src'/rel
 if p.exists():(p/'COLCON_IGNORE').touch()
template=(root/'esp32_toolchain.cmake.in').read_text()
for key,value in {'@IDF_TARGET@':target,'@IDF_PATH@':idf,'@CMAKE_C_COMPILER@':cc,'@CMAKE_CXX_COMPILER@':cxx,'@BUILD_CONFIG_DIR@':str(Path(config))}.items():template=template.replace(key,str(value).replace('\\','/'))
template='file(READ "'+str(root/'idf_include_flags.txt').replace('\\','/')+'" IDF_INCLUDES)\n'+template
(root/'native_toolchain.cmake').write_text(template)
run([python,'-m','colcon','build','--merge-install','--build-base','build-native','--install-base','install-native','--packages-up-to','rclc','nav_msgs','tf2_msgs','micro_ros_utilities','micro_ros_msgs','--metas',(root/'colcon.meta').as_posix(),'--cmake-args','-G','Ninja','-DCMAKE_MAKE_PROGRAM=C:/Espressif/tools/ninja/1.12.1/ninja.exe','-DBUILD_TESTING=OFF','-DBUILD_SHARED_LIBS=OFF','-DUCDR_SUPERBUILD=OFF','-DUCDR_ISOLATED_INSTALL=OFF','-DTHIRDPARTY=ON','-DCMAKE_BUILD_TYPE=Release','-DCMAKE_POSITION_INDEPENDENT_CODE=OFF','-DCMAKE_TOOLCHAIN_FILE='+(root/'native_toolchain.cmake').as_posix(),'-DCMAKE_C_STANDARD=17','-DUCLIENT_C_STANDARD=17','-DPython3_EXECUTABLE='+python],mcu)
install=mcu/'install-c'
archives=list((install/'lib').glob('*.a'))
if not archives:raise RuntimeError('No target static libraries produced')
# MRI merges archives without platform-dependent shell extraction/renaming.
mri='CREATE '+str(root/'libmicroros.a').replace('\\','/')+'\n'
for a in archives:mri+='ADDLIB '+str(a).replace('\\','/')+'\n'
mri+='SAVE\nEND\n'
subprocess.run([ar,'-M'],input=mri.encode(),check=True)
includes=root/'include';shutil.copytree(install/'include',includes,dirs_exist_ok=True)
for folder in list(includes.iterdir()):
 nested=folder/folder.name
 if nested.is_dir():shutil.copytree(nested,folder,dirs_exist_ok=True)
print('MICROROS_NATIVE_BUILD_COMPLETE',flush=True)
stamp.write_text(signature)
