import BaseIcon from '@ant-design/icons';

const Index = ({children, render, ...props}) => (
    <BaseIcon {...props}>
        {children}
    </BaseIcon>);
export default Index;