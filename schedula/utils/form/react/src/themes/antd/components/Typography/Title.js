import {Typography} from 'antd';

const Title = ({children, render, ...props}) => (
    <Typography.Title {...props}>
        {children}
    </Typography.Title>);
export default Title;