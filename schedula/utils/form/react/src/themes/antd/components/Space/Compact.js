import {Space} from 'antd';

const Compact = ({children, render, ...props}) => (
    <Space.Compact {...props}>
        {children}
    </Space.Compact>);
export default Compact;