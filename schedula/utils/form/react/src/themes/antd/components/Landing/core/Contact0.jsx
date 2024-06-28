import React from 'react';
import QueueAnim from 'rc-queue-anim';
import {HtmlContent} from './utils'

class Content10 extends React.PureComponent {
    constructor(props) {
        super(props);
        this.state = {
            showInfo: props.isMobile,
        };
    }

    onClick = () => {
        window.open(this.props.dataSource.Content.children.url.children);
    };

    markerEnter = () => {
        this.setState({
            showInfo: true,
        });
    };

    markerLeave = () => {
        this.setState({
            showInfo: false,
        });
    };

    render() {
        const {...props} = this.props;
        const {dataSource} = props;
        delete props.dataSource;
        delete props.isMobile;
        return (
            <div {...props} {...dataSource.wrapper}>
                <div
                    {...dataSource.Content}
                    onMouseEnter={this.markerEnter}
                    onMouseLeave={this.markerLeave}
                    onClick={this.onClick}
                    onTouchEnd={this.onClick}
                >
                    <div {...dataSource.Content.children.icon}>
                        <img src={dataSource.Content.children.icon.children}
                             alt="img"/>
                    </div>
                    <div {...dataSource.Content.children.iconShadow}>
                        <img
                            src={dataSource.Content.children.iconShadow.children}
                            alt="img"
                        />
                    </div>
                </div>
                <QueueAnim type="scale">
                    <div>
                        {this.state.showInfo && (
                            <div className="map-tip" key="map">
                                <h2>{HtmlContent(dataSource.Content.children.title.children)}</h2>
                                <p>{HtmlContent(dataSource.Content.children.content.children)}</p>
                            </div>
                        )}
                    </div>
                </QueueAnim>
            </div>
        );
    }
}

export default Content10;
