import {FloatButton as BaseFloatButton} from 'antd';

const FloatButton = ({children, render, ...props}) => (
    <BaseFloatButton {...props}>
        {children}
    </BaseFloatButton>);
export default FloatButton;