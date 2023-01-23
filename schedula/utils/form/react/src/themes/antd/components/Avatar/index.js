import {Avatar as BaseAvatar} from 'antd';

const Avatar = ({children, render, ...props}) => (
    <BaseAvatar {...props}>
        {children}
    </BaseAvatar>);
export default Avatar;