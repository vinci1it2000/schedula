import {Drawer as BaseDrawer} from 'antd';

const Drawer = ({children, render, ...props}) => (
    <BaseDrawer {...props}>
        {children}
    </BaseDrawer>);
export default Drawer;