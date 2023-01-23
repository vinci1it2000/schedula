import {Typography} from 'antd';

const Paragraph = ({children, render, ...props}) => (
    <Typography.Paragraph {...props}>
        {children}
    </Typography.Paragraph>);
export default Paragraph;