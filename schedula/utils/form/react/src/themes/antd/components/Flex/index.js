import {Flex as BaseFlex} from 'antd';

const Flex = ({children, render, ...props}) => (
    <BaseFlex {...props}>
        {children}
    </BaseFlex>);
export default Flex;