import {Spin} from 'antd';

const Loader = ({loading, children, ...props}) => {
    return <Spin spinning={loading} size="large"
                 style={{maxHeight: null}} {...props}>
        {children}
    </Spin>

};
export default Loader;