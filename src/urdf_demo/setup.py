from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'urdf_demo'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        # ament index marker
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        # 包元信息
        ('share/' + package_name, ['package.xml']),
        # launch 文件 -> share/urdf_demo/launch/
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.launch.py')),
        # URDF 文件 -> share/urdf_demo/urdf/
        (os.path.join('share', package_name, 'urdf'),
            glob('urdf/*.urdf') + glob('urdf/*.xacro')),
        # rviz 配置 -> share/urdf_demo/rviz/  (没有也没关系，glob 返回空列表)
        (os.path.join('share', package_name, 'rviz'),
            glob('rviz/*.rviz')),
        # mesh 资源 -> share/urdf_demo/meshes/
        (os.path.join('share', package_name, 'meshes'),
            glob('meshes/*.*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='root',
    maintainer_email='liuzhihaotina@163.com',
    description='URDF + robot_state_publisher + RViz2 demo',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        # 这个包只是发布 URDF 给 robot_state_publisher，
        # 没有自己的 Python 节点，所以 console_scripts 留空。
        'console_scripts': [
        ],
    },
)
