import {Skeleton as Base} from 'antd';

export function Skeleton({loading, children, ...props}) {
    return <Base loading={loading} active {...props}>
        {children}
    </Base>
}

export default Skeleton