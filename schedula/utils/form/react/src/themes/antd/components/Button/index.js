import {Button as BaseButton} from 'antd';

const Button = ({children, render, ...props}) => (
    <BaseButton {...props}>
        {children}
    </BaseButton>);
export default Button;