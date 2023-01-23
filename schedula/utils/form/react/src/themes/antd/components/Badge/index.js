import {Badge as BaseBadge} from 'antd';

const Badge = ({children, render, ...props}) => (
    <BaseBadge {...props}>
        {children}
    </BaseBadge>);
export default Badge;