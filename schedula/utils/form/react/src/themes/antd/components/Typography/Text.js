import {Typography} from 'antd';

const Text = ({children, render, ...props}) => (
    <Typography.Text {...props}>
        {children}
    </Typography.Text>);
export default Text;