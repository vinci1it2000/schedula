import {Divider as BaseDivider} from 'antd';

const Divider = ({children, render, ...props}) => (
    <BaseDivider {...props}>
        {children}
    </BaseDivider>);
export default Divider;