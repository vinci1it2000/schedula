import {Skeleton as BaseSkeleton} from 'antd';

const Skeleton = ({children, render, ...props}) => (
    <BaseSkeleton {...props}>
        {children}
    </BaseSkeleton>);
export default Skeleton;