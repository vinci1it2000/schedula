import {Avatar} from 'antd';

const {Group: BaseGroup} = Avatar,
    Group = ({children, render, ...props}) => (
        <BaseGroup {...props}>
            {children}
        </BaseGroup>);
export default Group;