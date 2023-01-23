import {Layout} from 'antd';

const {Sider: BaseSider} = Layout,
    Sider = ({children, render, ...props}) => (
        <BaseSider {...props}>
            {children}
        </BaseSider>);
export default Sider;