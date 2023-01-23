import {Space as BaseSpace} from 'antd';

const Space = ({children, render, ...props}) => (
    <BaseSpace {...props}>
        {children}
    </BaseSpace>);
export default Space;