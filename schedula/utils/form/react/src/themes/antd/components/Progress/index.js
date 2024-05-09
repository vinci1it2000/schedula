import {Progress as BaseProgress} from 'antd';

const Progress = ({children, render, ...props}) => (
    <BaseProgress {...props}>
        {children}
    </BaseProgress>);
export default Progress;